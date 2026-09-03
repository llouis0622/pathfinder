"""경로 오케스트레이션: 날씨 → 엔진 탐색 → 로그 저장 → 응답."""
from __future__ import annotations

import time
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import Settings
from ..models import RouteRequest, RouteResult
from ..schemas import NamedPoint, RouteSearchRequest, RouteSearchResponse, StoredRouteResponse
from . import engine_client
from .weather import get_weather


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


async def search_and_store(cfg: Settings, db: AsyncSession, req: RouteSearchRequest) -> RouteSearchResponse:
    started = time.perf_counter()
    mid_lat = (req.origin.lat + req.destination.lat) / 2
    mid_lng = (req.origin.lng + req.destination.lng) / 2
    weather = await get_weather(cfg, mid_lat, mid_lng, req.departure_at, req.weather_mode, req.manual_weather)
    payload = {
        "origin": {"lat": req.origin.lat, "lng": req.origin.lng},
        "destination": {"lat": req.destination.lat, "lng": req.destination.lng},
        "profile": req.profile,
        "departure_at": _iso(req.departure_at),
        "weather": weather.to_engine(),
        "options": {"k": req.options.k, "time_budget_s": req.options.time_budget_s, "seed": req.options.seed},
    }
    record = RouteRequest(
        origin_lat=req.origin.lat, origin_lng=req.origin.lng, origin_name=req.origin.name[:200],
        dest_lat=req.destination.lat, dest_lng=req.destination.lng, dest_name=req.destination.name[:200],
        profile=req.profile, departure_at=req.departure_at, weather_mode=req.weather_mode,
        weather=weather.model_dump(), options=req.options.model_dump(),
    )
    try:
        result = await engine_client.search(cfg, payload)
    except engine_client.EngineError as exc:
        record.status = "no_route" if exc.status == 422 else "error"
        record.error = exc.detail
        record.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        db.add(record)
        await db.commit()
        raise
    record.status = "ok"
    record.engine_metadata = result.get("metadata")
    record.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    for r in result.get("routes", []):
        record.results.append(RouteResult(
            rank=int(r["rank"]), summary=str(r.get("summary", ""))[:300], badges=r.get("badges"), cautions=r.get("cautions"),
            total_duration_min=float(r["total_duration_min"]), walk_distance_m=float(r["walk_distance_m"]),
            transfers=int(r.get("transfers", 0)), generalized_cost_s=(r.get("features") or {}).get("generalized_cost_s"), payload=r,
        ))
    db.add(record)
    await db.commit()
    metadata = dict(result.get("metadata", {}))
    metadata["backend_elapsed_ms"] = record.elapsed_ms
    return RouteSearchResponse(request_id=str(record.id), profile=req.profile, departure_at=_iso(req.departure_at),
                               weather=weather, routes=result.get("routes", []), metadata=metadata)


async def get_stored(db: AsyncSession, request_id: uuid.UUID) -> StoredRouteResponse | None:
    stmt = select(RouteRequest).where(RouteRequest.id == request_id).options(selectinload(RouteRequest.results))
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        return None
    return StoredRouteResponse(
        request_id=str(record.id), created_at=record.created_at.isoformat(), profile=record.profile, status=record.status,
        origin=NamedPoint(lat=record.origin_lat, lng=record.origin_lng, name=record.origin_name),
        destination=NamedPoint(lat=record.dest_lat, lng=record.dest_lng, name=record.dest_name),
        weather=record.weather, routes=[r.payload for r in record.results], metadata=record.engine_metadata,
    )
