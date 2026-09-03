"""경로 오케스트레이션: 날씨 → 엔진 탐색 → (로그인 시) 개인화 재정렬 → 로그 저장 → 응답. 선택 기록으로 정책 학습."""
from __future__ import annotations

import random
import time
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import Settings
from ..models import EdgeOverride, EngineRun, PolicyUpdate, RouteChoice, RouteRequest, RouteResult, User, UserPolicy
from ..observability import ENGINE_LATENCY, ROUTE_CHOICES, ROUTE_SEARCHES, SEARCH_CACHE
from ..schemas import ChooseResponse, NamedPoint, RouteSearchRequest, RouteSearchResponse, StoredRouteResponse
from . import engine_client
from .cache import SearchCache, search_key
from .personalization import Policy, rerank, update
from .weather import get_weather

KST = ZoneInfo("Asia/Seoul")


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


async def load_policy(db: AsyncSession, user_id: uuid.UUID) -> tuple[Policy, UserPolicy | None]:
    row = await db.get(UserPolicy, user_id)
    return (Policy.from_dict(row.policy) if row else Policy()), row


async def save_policy(db: AsyncSession, user_id: uuid.UUID, policy: Policy, row: UserPolicy | None) -> None:
    if row is None:
        row = UserPolicy(user_id=user_id)
        db.add(row)
    row.policy = policy.to_dict()
    row.updates = policy.updates


async def active_overrides(db: AsyncSession) -> list[dict]:
    """활성이고 만료되지 않은 엣지 오버라이드 (엔진에 그대로 전달)."""
    now = datetime.now(timezone.utc)
    rows = (await db.execute(select(EdgeOverride.edge_id, EdgeOverride.kind, EdgeOverride.expires_at).where(EdgeOverride.active.is_(True)))).all()
    out = []
    for edge_id, kind, expires_at in rows:
        if expires_at is not None:
            exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
            if exp < now:
                continue
        out.append({"edge_id": int(edge_id), "kind": kind})
    return out


async def search_and_store(cfg: Settings, db: AsyncSession, req: RouteSearchRequest, user: User | None = None,
                           rng: random.Random | None = None, cache: SearchCache | None = None) -> RouteSearchResponse:
    started = time.perf_counter()
    mid_lat = (req.origin.lat + req.destination.lat) / 2
    mid_lng = (req.origin.lng + req.destination.lng) / 2
    departure_at = req.departure_at or datetime.now(KST)
    weather = await get_weather(cfg, mid_lat, mid_lng, departure_at)
    payload = {
        "origin": {"lat": req.origin.lat, "lng": req.origin.lng},
        "destination": {"lat": req.destination.lat, "lng": req.destination.lng},
        "profile": req.profile,
        "departure_at": _iso(departure_at),
        "weather": weather.to_engine(),
        "preferences": {"avoid_slope": True, "prefer_shade": req.prefer_shade},
        "options": {"k": req.options.k, "time_budget_s": req.options.time_budget_s, "seed": req.options.seed},
        "overrides": await active_overrides(db),
    }
    record = RouteRequest(
        user_id=(user.id if user else None),
        origin_lat=req.origin.lat, origin_lng=req.origin.lng, origin_name=req.origin.name[:200],
        dest_lat=req.destination.lat, dest_lng=req.destination.lng, dest_name=req.destination.name[:200],
        profile=req.profile, departure_at=departure_at, weather_mode="auto",
        weather=weather.model_dump(), options={**req.options.model_dump(), "prefer_shade": req.prefer_shade},
    )
    key = search_key((req.origin.lat, req.origin.lng), (req.destination.lat, req.destination.lng), req.profile, req.prefer_shade,
                     departure_at, weather.flags, req.options.k)
    cached = False
    result = cache.get(key) if cache is not None else None
    if result is not None:
        cached = True
        SEARCH_CACHE.labels("hit").inc()
    else:
        if cache is not None and cache.enabled:
            SEARCH_CACHE.labels("miss").inc()
        engine_started = time.perf_counter()
        try:
            result = await engine_client.search(cfg, payload)
        except engine_client.EngineError as exc:
            record.status = "no_route" if exc.status == 422 else "error"
            record.error = exc.detail
            record.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            db.add(record)
            await db.commit()
            ROUTE_SEARCHES.labels(req.profile, record.status, "false").inc()
            raise
        ENGINE_LATENCY.observe(time.perf_counter() - engine_started)
        if cache is not None:
            cache.put(key, result)
    routes = list(result.get("routes", []))
    personalized = False
    if user is not None and cfg.personalization_enabled and len(routes) >= 2:
        policy, _ = await load_policy(db, user.id)
        rr = rerank(policy, routes, rng=rng, epsilon=cfg.personalization_epsilon)
        if rr.applied:
            routes = rr.routes
            personalized = True
            record.personalized = True
            record.explored = rr.explored
            record.propensities = rr.propensities
    record.status = "ok"
    record.engine_metadata = result.get("metadata")
    record.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    for r in routes:
        record.results.append(RouteResult(
            rank=int(r["rank"]), engine_rank=int(r.get("engine_rank", r["rank"])), summary=str(r.get("summary", ""))[:300],
            badges=r.get("badges"), cautions=r.get("cautions"), total_duration_min=float(r["total_duration_min"]),
            walk_distance_m=float(r["walk_distance_m"]), transfers=int(r.get("transfers", 0)),
            generalized_cost_s=(r.get("features") or {}).get("generalized_cost_s"), payload=r,
        ))
    db.add(record)
    run = None if cached else _engine_run(record, result.get("metadata") or {}, len(routes), req.options.k)
    if run is not None:
        db.add(run)
    await db.commit()
    ROUTE_SEARCHES.labels(req.profile, "ok", "true" if cached else "false").inc()
    metadata = dict(result.get("metadata", {}))
    metadata["backend_elapsed_ms"] = record.elapsed_ms
    metadata["personalized"] = personalized
    metadata["cached"] = cached
    return RouteSearchResponse(request_id=str(record.id), profile=req.profile, departure_at=_iso(departure_at),
                               prefer_shade=req.prefer_shade, weather=weather, routes=routes, metadata=metadata, personalized=personalized)


def _engine_run(record: RouteRequest, meta: dict, routes_returned: int, k: int) -> EngineRun | None:
    """엔진 metadata 를 성능 로그 행으로 펼친다 (metadata 가 없으면 None)."""
    if not meta:
        return None
    aco = meta.get("aco") or {}
    ga = meta.get("ga") or {}
    return EngineRun(
        request=record, profile=record.profile, k=k,
        corridor_nodes=int(meta.get("corridor_nodes") or 0), corridor_edges=int(meta.get("corridor_edges") or 0),
        blocked_edges=int(meta.get("blocked_edges") or 0),
        snap_origin_m=meta.get("snap_origin_m"), snap_destination_m=meta.get("snap_destination_m"),
        aco_iterations=int(aco.get("iterations") or 0), aco_ants_completed=int(aco.get("ants_completed") or 0),
        aco_ants_failed=int(aco.get("ants_failed") or 0), aco_stopped_by=str(aco.get("stopped_by") or "")[:32],
        aco_elapsed_ms=aco.get("elapsed_ms"), ga_enabled=bool(ga.get("enabled", bool(ga))),
        ga_generations=int(ga.get("generations") or 0), ga_elapsed_ms=ga.get("elapsed_ms"),
        archive_size=int(meta.get("archive_size") or 0), routes_returned=routes_returned,
        engine_elapsed_ms=meta.get("elapsed_ms"), backend_elapsed_ms=record.elapsed_ms,
        shade_status=str(meta.get("shade_status") or "")[:32], weather_flags=list(meta.get("weather_flags") or []),
    )


async def record_choice(cfg: Settings, db: AsyncSession, request_id: uuid.UUID, route_id: str, user: User | None) -> ChooseResponse | None:
    """사용자가 고른 경로를 저장하고, 로그인 사용자면 정책을 갱신한다. 요청이 없으면 None."""
    stmt = select(RouteRequest).where(RouteRequest.id == request_id).options(selectinload(RouteRequest.results))
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        return None
    results = sorted(record.results, key=lambda r: r.rank)
    chosen = next((r for r in results if r.payload.get("id") == route_id), None)
    if chosen is None:
        raise ValueError("해당 요청에 없는 경로입니다")
    if user is not None and record.user_id not in (None, user.id):
        raise PermissionError("다른 사용자의 요청입니다")
    propensity = (record.propensities or {}).get(route_id) if record.propensities else None
    choice = RouteChoice(request_id=record.id, user_id=(user.id if user else None), route_id=route_id, shown_rank=chosen.rank,
                         propensity=propensity, learned=False)
    learned = False
    updates = 0
    summary: list[str] = []
    if user is not None and cfg.personalization_enabled and len(results) >= 2:
        policy, row = await load_policy(db, user.id)
        new_policy = update(policy, [r.payload for r in results], route_id)
        learned = new_policy.updates > policy.updates
        if learned:
            await save_policy(db, user.id, new_policy, row)
            db.add(PolicyUpdate(user_id=user.id, request_id=record.id, route_id=route_id, shown_rank=chosen.rank,
                                engine_rank=chosen.engine_rank, explored=bool(record.explored), updates_after=new_policy.updates,
                                weights_before={k: round(v, 4) for k, v in policy.weights.items()},
                                weights_after={k: round(v, 4) for k, v in new_policy.weights.items()}))
        updates = new_policy.updates
        summary = new_policy.summary()
        choice.learned = learned
    db.add(choice)
    await db.commit()
    ROUTE_CHOICES.labels(str(chosen.rank), "true" if learned else "false").inc()
    return ChooseResponse(recorded=True, learned=learned, updates=updates, summary=summary)


async def get_stored(db: AsyncSession, request_id: uuid.UUID) -> StoredRouteResponse | None:
    stmt = select(RouteRequest).where(RouteRequest.id == request_id).options(selectinload(RouteRequest.results))
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        return None
    return StoredRouteResponse(
        request_id=str(record.id), created_at=record.created_at.isoformat(), profile=record.profile, status=record.status,
        origin=NamedPoint(lat=record.origin_lat, lng=record.origin_lng, name=record.origin_name),
        destination=NamedPoint(lat=record.dest_lat, lng=record.dest_lng, name=record.dest_name),
        weather=record.weather, routes=[r.payload for r in sorted(record.results, key=lambda r: r.rank)], metadata=record.engine_metadata,
    )
