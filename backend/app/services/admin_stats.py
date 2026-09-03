"""관리자 분석 집계: 대시보드, 이용 추이, 경로 품질, 공간 분석, 취향 분포, 엔진 성능.

기간 창 안의 행을 가벼운 열만 골라 읽고 Python 으로 집계한다 (PostgreSQL/SQLite 공통, KST 일 단위 버킷).
"""
from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ApiAccessLog, EngineRun, PlaceSearch, PolicyUpdate, RouteChoice, RouteRequest, RouteResult, User, UserPolicy
from .personalization import FEATURE_LABELS, FEATURES, Policy

KST = ZoneInfo("Asia/Seoul")
PROFILE_LABELS = {"wheelchair": "휠체어", "elderly": "고령자", "walking_aid": "보행보조", "visually_impaired": "시각장애"}
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


# ---------------------------------------------------------------- 공통
def aware(dt: datetime | None) -> datetime | None:
    """SQLite 는 tz 를 잃고 naive 로 돌려주므로 UTC 로 간주한다."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def iso(dt: datetime | None) -> str | None:
    dt = aware(dt)
    return dt.isoformat() if dt else None


def day_key(dt: datetime) -> str:
    return aware(dt).astimezone(KST).strftime("%Y-%m-%d")


def window(days: int) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    start = (now.astimezone(KST) - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    return start, now


def day_range(start: datetime, end: datetime) -> list[str]:
    keys: list[str] = []
    cur = aware(start).astimezone(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    last = aware(end).astimezone(KST)
    while cur <= last:
        keys.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return keys


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 1)


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def user_out(u: User | None) -> dict | None:
    if u is None:
        return None
    return {"id": str(u.id), "provider": u.provider, "nickname": u.nickname, "avatar_url": u.avatar_url,
            "created_at": iso(u.created_at), "last_login_at": iso(u.last_login_at)}


def request_row(r: RouteRequest, user: User | None = None, n_results: int | None = None, chosen_rank: int | None = None) -> dict:
    return {
        "id": str(r.id), "created_at": iso(r.created_at), "user": user_out(user), "user_id": (str(r.user_id) if r.user_id else None),
        "profile": r.profile, "profile_label": PROFILE_LABELS.get(r.profile, r.profile),
        "origin": {"lat": r.origin_lat, "lng": r.origin_lng, "name": r.origin_name},
        "destination": {"lat": r.dest_lat, "lng": r.dest_lng, "name": r.dest_name},
        "status": r.status, "error": r.error, "elapsed_ms": r.elapsed_ms, "personalized": r.personalized, "explored": r.explored,
        "prefer_shade": bool((r.options or {}).get("prefer_shade")), "weather_flags": list((r.weather or {}).get("flags") or []),
        "departure_at": iso(r.departure_at), "n_results": n_results, "chosen_rank": chosen_rank,
    }


async def users_by_id(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, User]:
    if not ids:
        return {}
    rows = (await db.execute(select(User).where(User.id.in_(list(ids))))).scalars().all()
    return {u.id: u for u in rows}


async def choices_by_request(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, RouteChoice]:
    if not ids:
        return {}
    rows = (await db.execute(select(RouteChoice).where(RouteChoice.request_id.in_(ids)).order_by(RouteChoice.created_at))).scalars().all()
    return {c.request_id: c for c in rows}


# ---------------------------------------------------------------- 대시보드
async def overview(db: AsyncSession) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    today_start = now.astimezone(KST).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    d7, _ = window(7)
    d30, _ = window(30)

    async def count(stmt) -> int:
        return int((await db.execute(stmt)).scalar_one() or 0)

    requests_total = await count(select(func.count(RouteRequest.id)))
    requests_today = await count(select(func.count(RouteRequest.id)).where(RouteRequest.created_at >= today_start))
    users_total = await count(select(func.count(User.id)))
    users_new_7d = await count(select(func.count(User.id)).where(User.created_at >= d7))
    learned_users = await count(select(func.count(UserPolicy.user_id)).where(UserPolicy.updates > 0))
    access_errors_24h = await count(select(func.count(ApiAccessLog.id)).where(ApiAccessLog.created_at >= now - timedelta(hours=24),
                                                                              ApiAccessLog.status >= 500))

    reqs = (await db.execute(select(RouteRequest.id, RouteRequest.created_at, RouteRequest.user_id, RouteRequest.status,
                                    RouteRequest.personalized, RouteRequest.elapsed_ms, RouteRequest.profile)
                             .where(RouteRequest.created_at >= d30))).all()
    choices = (await db.execute(select(RouteChoice.request_id, RouteChoice.created_at, RouteChoice.user_id)
                                .where(RouteChoice.created_at >= d30))).all()
    keys = day_range(d30, now)
    per_day: dict[str, dict[str, Any]] = {k: {"date": k, "requests": 0, "choices": 0, "users": set()} for k in keys}
    r7 = [r for r in reqs if aware(r.created_at) >= d7]
    c7 = [c for c in choices if aware(c.created_at) >= d7]
    for r in reqs:
        k = day_key(r.created_at)
        if k in per_day:
            per_day[k]["requests"] += 1
            if r.user_id:
                per_day[k]["users"].add(r.user_id)
    for c in choices:
        k = day_key(c.created_at)
        if k in per_day:
            per_day[k]["choices"] += 1
    series = [{"date": v["date"], "requests": v["requests"], "choices": v["choices"], "users": len(v["users"])} for v in per_day.values()]
    ok7 = [r for r in r7 if r.status == "ok"]
    profile_share = Counter(r.profile for r in reqs)

    recent_reqs = (await db.execute(select(RouteRequest).order_by(RouteRequest.created_at.desc()).limit(8))).scalars().all()
    users = await users_by_id(db, {r.user_id for r in recent_reqs if r.user_id})
    chosen = await choices_by_request(db, [r.id for r in recent_reqs])
    recent_auth = (await db.execute(select(ApiAccessLog).where(ApiAccessLog.kind.in_(["auth", "admin"]))
                                    .order_by(ApiAccessLog.created_at.desc()).limit(8))).scalars().all()
    auth_users = await users_by_id(db, {a.user_id for a in recent_auth if a.user_id})
    return {
        "generated_at": now.isoformat(),
        "kpis": {
            "requests_total": requests_total, "requests_today": requests_today, "requests_7d": len(r7),
            "users_total": users_total, "users_new_7d": users_new_7d, "active_users_7d": len({r.user_id for r in r7 if r.user_id}),
            "choices_7d": len(c7), "choose_rate_7d": rate(len(c7), len(ok7)),
            "personalized_share_7d": rate(sum(1 for r in ok7 if r.personalized), len(ok7)),
            "no_route_rate_7d": rate(sum(1 for r in r7 if r.status == "no_route"), len(r7)),
            "error_rate_7d": rate(sum(1 for r in r7 if r.status == "error"), len(r7)),
            "avg_elapsed_ms_7d": mean([float(r.elapsed_ms) for r in ok7 if r.elapsed_ms is not None]),
            "learned_users": learned_users, "access_errors_24h": access_errors_24h,
        },
        "series": series,
        "profile_share": [{"profile": p, "label": PROFILE_LABELS.get(p, p), "count": n} for p, n in profile_share.most_common()],
        "recent_requests": [request_row(r, users.get(r.user_id), None, (chosen[r.id].shown_rank if r.id in chosen else None)) for r in recent_reqs],
        "recent_auth": [access_row(a, auth_users.get(a.user_id)) for a in recent_auth],
    }


def access_row(a: ApiAccessLog, user: User | None = None) -> dict:
    return {"id": str(a.id), "created_at": iso(a.created_at), "kind": a.kind, "method": a.method, "path": a.path, "status": a.status,
            "duration_ms": a.duration_ms, "user": user_out(user), "user_id": (str(a.user_id) if a.user_id else None), "ip": a.ip,
            "user_agent": a.user_agent, "detail": a.detail}


# ---------------------------------------------------------------- 이용 추이
async def usage(db: AsyncSession, days: int) -> dict[str, Any]:
    start, end = window(days)
    reqs = (await db.execute(select(RouteRequest.id, RouteRequest.created_at, RouteRequest.user_id, RouteRequest.status,
                                    RouteRequest.profile, RouteRequest.options, RouteRequest.weather)
                             .where(RouteRequest.created_at >= start))).all()
    choices = (await db.execute(select(RouteChoice.created_at).where(RouteChoice.created_at >= start))).all()
    new_users = (await db.execute(select(User.created_at).where(User.created_at >= start))).all()
    places = (await db.execute(select(PlaceSearch.query, PlaceSearch.source, PlaceSearch.result_count)
                               .where(PlaceSearch.created_at >= start))).all()
    keys = day_range(start, end)
    daily = {k: {"date": k, "requests": 0, "ok": 0, "no_route": 0, "error": 0, "choices": 0, "users": set(), "new_users": 0} for k in keys}
    hourly = [0] * 24
    weekday = [0] * 7
    flags: Counter[str] = Counter()
    shade_on = 0
    for r in reqs:
        k = day_key(r.created_at)
        local = aware(r.created_at).astimezone(KST)
        hourly[local.hour] += 1
        weekday[local.weekday()] += 1
        if k in daily:
            d = daily[k]
            d["requests"] += 1
            d[r.status if r.status in ("ok", "no_route", "error") else "error"] += 1
            if r.user_id:
                d["users"].add(r.user_id)
        if (r.options or {}).get("prefer_shade"):
            shade_on += 1
        for f in (r.weather or {}).get("flags") or []:
            flags[f] += 1
    for c in choices:
        k = day_key(c.created_at)
        if k in daily:
            daily[k]["choices"] += 1
    for u in new_users:
        k = day_key(u.created_at)
        if k in daily:
            daily[k]["new_users"] += 1
    profile = Counter(r.profile for r in reqs)
    status = Counter(r.status for r in reqs)
    top_queries = Counter(p.query.strip() for p in places if p.query.strip())
    return {
        "days": days, "start": start.isoformat(), "end": end.isoformat(), "total_requests": len(reqs),
        "daily": [{**{k: v for k, v in d.items() if k != "users"}, "users": len(d["users"])} for d in daily.values()],
        "hourly": [{"hour": h, "count": n} for h, n in enumerate(hourly)],
        "weekday": [{"weekday": i, "label": WEEKDAYS[i], "count": n} for i, n in enumerate(weekday)],
        "profile_share": [{"profile": p, "label": PROFILE_LABELS.get(p, p), "count": n} for p, n in profile.most_common()],
        "status_share": [{"status": s, "count": n} for s, n in status.most_common()],
        "prefer_shade": {"on": shade_on, "off": len(reqs) - shade_on},
        "weather_flags": [{"flag": f, "count": n} for f, n in flags.most_common()],
        "place_searches": {"total": len(places), "no_result": sum(1 for p in places if p.result_count == 0),
                           "sources": [{"source": s, "count": n} for s, n in Counter(p.source for p in places).most_common()],
                           "top_queries": [{"query": q, "count": n} for q, n in top_queries.most_common(15)]},
    }


# ---------------------------------------------------------------- 경로 품질
async def quality(db: AsyncSession, days: int) -> dict[str, Any]:
    start, _ = window(days)
    reqs = (await db.execute(select(RouteRequest.id, RouteRequest.status, RouteRequest.profile, RouteRequest.personalized,
                                    RouteRequest.explored, RouteRequest.elapsed_ms, RouteRequest.user_id)
                             .where(RouteRequest.created_at >= start))).all()
    req_by_id = {r.id: r for r in reqs}
    ids = list(req_by_id)
    results = []
    choices = []
    if ids:
        results = (await db.execute(select(RouteResult.request_id, RouteResult.rank, RouteResult.engine_rank, RouteResult.badges,
                                           RouteResult.cautions, RouteResult.total_duration_min, RouteResult.walk_distance_m,
                                           RouteResult.transfers).where(RouteResult.request_id.in_(ids)))).all()
        choices = (await db.execute(select(RouteChoice.request_id, RouteChoice.shown_rank, RouteChoice.user_id, RouteChoice.learned)
                                    .where(RouteChoice.request_id.in_(ids)))).all()
    shown_by_rank: Counter[int] = Counter(r.rank for r in results)
    chosen_by_rank: Counter[int] = Counter(c.shown_rank for c in choices)
    engine_rank_of = {(r.request_id, r.rank): (r.engine_rank or r.rank) for r in results}
    shown_by_engine: Counter[int] = Counter((r.engine_rank or r.rank) for r in results)
    chosen_by_engine: Counter[int] = Counter(engine_rank_of.get((c.request_id, c.shown_rank), c.shown_rank) for c in choices)

    def rank_table(shown: Counter, chosen: Counter) -> list[dict]:
        return [{"rank": k, "shown": shown[k], "chosen": chosen[k], "rate": rate(chosen[k], shown[k])} for k in sorted(shown)]

    groups = {"personalized": [], "plain": [], "explored": []}
    for c in choices:
        r = req_by_id.get(c.request_id)
        if r is None:
            continue
        groups["personalized" if r.personalized else "plain"].append(c.shown_rank)
        if r.explored:
            groups["explored"].append(c.shown_rank)
    compare = {g: {"choices": len(v), "rank1_hit_rate": rate(sum(1 for x in v if x == 1), len(v))} for g, v in groups.items()}

    per_profile: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in results:
        if r.rank != 1:
            continue
        p = req_by_id[r.request_id].profile
        per_profile[p]["duration"].append(float(r.total_duration_min))
        per_profile[p]["walk"].append(float(r.walk_distance_m))
        per_profile[p]["transfers"].append(float(r.transfers))
    prof_rows = []
    for p in sorted({r.profile for r in reqs}):
        rs = [r for r in reqs if r.profile == p]
        prof_rows.append({
            "profile": p, "label": PROFILE_LABELS.get(p, p), "requests": len(rs),
            "no_route_rate": rate(sum(1 for r in rs if r.status == "no_route"), len(rs)),
            "avg_elapsed_ms": mean([float(r.elapsed_ms) for r in rs if r.elapsed_ms is not None]),
            "avg_duration_min": mean(per_profile[p]["duration"]), "avg_walk_m": mean(per_profile[p]["walk"]),
            "avg_transfers": mean(per_profile[p]["transfers"]),
        })
    badges: Counter[str] = Counter()
    cautions: Counter[str] = Counter()
    for r in results:
        for b in r.badges or []:
            badges[str(b)] += 1
        for c in r.cautions or []:
            cautions[str(c)] += 1
    ok = [r for r in reqs if r.status == "ok"]
    return {
        "days": days, "requests": len(reqs), "ok": len(ok), "choices": len(choices),
        "choose_rate": rate(len(choices), len(ok)), "learned_choices": sum(1 for c in choices if c.learned),
        "by_shown_rank": rank_table(shown_by_rank, chosen_by_rank), "by_engine_rank": rank_table(shown_by_engine, chosen_by_engine),
        "compare": compare, "per_profile": prof_rows,
        "badges": [{"key": k, "count": n} for k, n in badges.most_common(12)],
        "cautions": [{"key": k, "count": n} for k, n in cautions.most_common(12)],
    }


# ---------------------------------------------------------------- 공간 분석
def _place_key(name: str, lat: float, lng: float) -> str:
    return name.strip() or f"{lat:.4f}, {lng:.4f}"


async def spatial(db: AsyncSession, days: int) -> dict[str, Any]:
    start, _ = window(days)
    reqs = (await db.execute(select(RouteRequest.id, RouteRequest.origin_name, RouteRequest.origin_lat, RouteRequest.origin_lng,
                                    RouteRequest.dest_name, RouteRequest.dest_lat, RouteRequest.dest_lng, RouteRequest.status)
                             .where(RouteRequest.created_at >= start))).all()
    origins: Counter[str] = Counter()
    dests: Counter[str] = Counter()
    pairs: Counter[tuple[str, str]] = Counter()
    coords: dict[str, tuple[float, float]] = {}
    no_route_pairs: Counter[tuple[str, str]] = Counter()
    for r in reqs:
        o = _place_key(r.origin_name, r.origin_lat, r.origin_lng)
        d = _place_key(r.dest_name, r.dest_lat, r.dest_lng)
        origins[o] += 1
        dests[d] += 1
        pairs[(o, d)] += 1
        coords.setdefault(o, (r.origin_lat, r.origin_lng))
        coords.setdefault(d, (r.dest_lat, r.dest_lng))
        if r.status == "no_route":
            no_route_pairs[(o, d)] += 1
    ids = [r.id for r in reqs]
    stations: Counter[str] = Counter()
    lines: Counter[str] = Counter()
    unverified: Counter[str] = Counter()
    facilities: Counter[str] = Counter()
    if ids:
        payloads = (await db.execute(select(RouteResult.payload).where(RouteResult.request_id.in_(ids), RouteResult.rank == 1))).all()
        for (payload,) in payloads:
            for leg in (payload or {}).get("legs") or []:
                kind = leg.get("kind")
                if kind == "ride":
                    for n in (leg.get("from_name"), leg.get("to_name")):
                        if n:
                            stations[n] += 1
                    if leg.get("route_name"):
                        lines[leg["route_name"]] += 1
                elif kind == "vertical":
                    facilities[leg.get("facility") or "unknown"] += 1
                    if leg.get("verified") is not True and leg.get("station_name"):
                        unverified[leg["station_name"]] += 1

    def places(counter: Counter[str]) -> list[dict]:
        return [{"name": n, "count": c, "lat": coords[n][0], "lng": coords[n][1]} for n, c in counter.most_common(15)]

    return {
        "days": days, "requests": len(reqs),
        "top_origins": places(origins), "top_destinations": places(dests),
        "top_pairs": [{"origin": o, "destination": d, "count": c, "no_route": no_route_pairs[(o, d)]} for (o, d), c in pairs.most_common(15)],
        "top_stations": [{"name": n, "count": c} for n, c in stations.most_common(15)],
        "lines": [{"name": n, "count": c} for n, c in lines.most_common(10)],
        "facilities": [{"facility": f, "count": c} for f, c in facilities.most_common()],
        "unverified_stations": [{"name": n, "count": c} for n, c in unverified.most_common(10)],
    }


# ---------------------------------------------------------------- 취향 분포
def policy_out(policy: Policy) -> dict:
    return {"updates": policy.updates, "weights": {k: round(v, 3) for k, v in policy.weights.items()}, "summary": policy.summary()}


async def preferences(db: AsyncSession) -> dict[str, Any]:
    rows = (await db.execute(select(UserPolicy, User).join(User, User.id == UserPolicy.user_id).order_by(UserPolicy.updated_at.desc()))).all()
    learned = [(p, u) for p, u in rows if p.updates > 0]
    per_feature = []
    for f in FEATURES:
        ws = [float(Policy.from_dict(p.policy).weights.get(f, 0.0)) for p, _ in learned]
        pos, neg = FEATURE_LABELS[f]
        per_feature.append({"feature": f, "positive_label": pos, "negative_label": neg, "mean": mean(ws) if ws else 0.0,
                            "positive_users": sum(1 for w in ws if w >= 0.25), "negative_users": sum(1 for w in ws if w <= -0.25)})
    labels: Counter[str] = Counter()
    users = []
    for p, u in learned:
        policy = Policy.from_dict(p.policy)
        for s in policy.summary():
            labels[s] += 1
        users.append({"user": user_out(u), **policy_out(policy), "updated_at": iso(p.updated_at)})
    hist = Counter(min(p.updates, 20) // 5 for p, _ in learned)
    return {
        "learned_users": len(learned), "total_policies": len(rows),
        "per_feature": per_feature,
        "labels": [{"label": k, "count": n} for k, n in labels.most_common()],
        "updates_histogram": [{"bucket": f"{b * 5}~{b * 5 + 4}" if b < 4 else "20+", "count": hist[b]} for b in range(5)],
        "users": users,
    }


# ---------------------------------------------------------------- 엔진 성능
async def engine_stats(db: AsyncSession, days: int) -> dict[str, Any]:
    start, end = window(days)
    runs = (await db.execute(select(EngineRun).where(EngineRun.created_at >= start))).scalars().all()

    def block(rs: list[EngineRun]) -> dict:
        eng = [float(r.engine_elapsed_ms) for r in rs if r.engine_elapsed_ms is not None]
        aco = [float(r.aco_elapsed_ms) for r in rs if r.aco_elapsed_ms is not None]
        ga = [float(r.ga_elapsed_ms) for r in rs if r.ga_elapsed_ms is not None]
        back = [float(r.backend_elapsed_ms) for r in rs if r.backend_elapsed_ms is not None]
        ants = sum(r.aco_ants_completed + r.aco_ants_failed for r in rs)
        return {
            "runs": len(rs), "engine_p50_ms": percentile(eng, 0.5), "engine_p95_ms": percentile(eng, 0.95),
            "backend_p50_ms": percentile(back, 0.5), "aco_p50_ms": percentile(aco, 0.5), "ga_p50_ms": percentile(ga, 0.5),
            "avg_iterations": mean([float(r.aco_iterations) for r in rs]), "avg_generations": mean([float(r.ga_generations) for r in rs]),
            "ant_fail_ratio": rate(sum(r.aco_ants_failed for r in rs), ants),
            "avg_corridor_nodes": mean([float(r.corridor_nodes) for r in rs]), "avg_corridor_edges": mean([float(r.corridor_edges) for r in rs]),
            "avg_blocked_edges": mean([float(r.blocked_edges) for r in rs]), "avg_archive": mean([float(r.archive_size) for r in rs]),
            "stopped_by": [{"reason": k, "count": n} for k, n in Counter(r.aco_stopped_by or "unknown" for r in rs).most_common()],
        }

    keys = day_range(start, end)
    per_day: dict[str, list[float]] = {k: [] for k in keys}
    for r in runs:
        k = day_key(r.created_at)
        if k in per_day and r.engine_elapsed_ms is not None:
            per_day[k].append(float(r.engine_elapsed_ms))
    return {
        "days": days, "summary": block(list(runs)),
        "per_profile": [{"profile": p, "label": PROFILE_LABELS.get(p, p), **block([r for r in runs if r.profile == p])}
                        for p in sorted({r.profile for r in runs})],
        "daily": [{"date": k, "runs": len(v), "p50_ms": percentile(v, 0.5), "p95_ms": percentile(v, 0.95)} for k, v in per_day.items()],
        "shade_status": [{"status": k, "count": n} for k, n in Counter(r.shade_status or "unknown" for r in runs).most_common()],
    }


def engine_row(r: EngineRun, req: RouteRequest | None = None) -> dict:
    return {
        "id": str(r.id), "created_at": iso(r.created_at), "request_id": str(r.request_id), "profile": r.profile,
        "profile_label": PROFILE_LABELS.get(r.profile, r.profile),
        "origin_name": (req.origin_name if req else ""), "dest_name": (req.dest_name if req else ""), "k": r.k,
        "corridor_nodes": r.corridor_nodes, "corridor_edges": r.corridor_edges, "blocked_edges": r.blocked_edges,
        "snap_origin_m": r.snap_origin_m, "snap_destination_m": r.snap_destination_m,
        "aco": {"iterations": r.aco_iterations, "ants_completed": r.aco_ants_completed, "ants_failed": r.aco_ants_failed,
                "stopped_by": r.aco_stopped_by, "elapsed_ms": r.aco_elapsed_ms},
        "ga": {"enabled": r.ga_enabled, "generations": r.ga_generations, "elapsed_ms": r.ga_elapsed_ms},
        "archive_size": r.archive_size, "routes_returned": r.routes_returned, "engine_elapsed_ms": r.engine_elapsed_ms,
        "backend_elapsed_ms": r.backend_elapsed_ms, "shade_status": r.shade_status, "weather_flags": r.weather_flags or [],
    }


def policy_update_row(p: PolicyUpdate) -> dict:
    return {"id": str(p.id), "created_at": iso(p.created_at), "user_id": str(p.user_id), "request_id": (str(p.request_id) if p.request_id else None),
            "route_id": p.route_id, "shown_rank": p.shown_rank, "engine_rank": p.engine_rank, "explored": p.explored,
            "updates_after": p.updates_after, "weights_before": p.weights_before or {}, "weights_after": p.weights_after or {}}


def choice_row(c: RouteChoice, req: RouteRequest | None = None, user: User | None = None) -> dict:
    return {"id": str(c.id), "created_at": iso(c.created_at), "request_id": str(c.request_id), "user": user_out(user),
            "user_id": (str(c.user_id) if c.user_id else None), "route_id": c.route_id, "shown_rank": c.shown_rank,
            "propensity": c.propensity, "learned": c.learned,
            "origin_name": (req.origin_name if req else ""), "dest_name": (req.dest_name if req else ""),
            "profile": (req.profile if req else ""), "personalized": (bool(req.personalized) if req else False),
            "explored": (bool(req.explored) if req else False)}


# ---------------------------------------------------------------- 개인화 오프라인 평가 (IPS)
def ips_from_samples(samples: list[dict[str, Any]], epsilon: float) -> dict[str, Any]:
    """로그된 propensity 로 두 정책(엔진 순위, 개인화 탐욕)의 1순위 적중률을 역확률 가중으로 추정한다.

    sample = {shown: 1순위로 보인 route id, chosen: 고른 route id, engine: 엔진 1순위 id, greedy: 정책 argmax id,
              propensities: {id: π(id)}, explored: bool}
    행동 = 1순위에 놓은 경로. 로깅 확률 p_b(a) = (1-ε)·1[a = greedy] + ε·π(a) (ε-greedy 혼합).
    보상 r = 1[chosen == shown]. 대상 정책은 결정적이므로 π_t(a) = 1[a = a_t].
    IPS = 평균(r·w), SNIPS = Σ(r·w)/Σw, w = 1[a_t = shown]/p_b(shown). ESS 로 신뢰도를 본다.
    """
    eps = max(0.0, min(1.0, float(epsilon)))
    n = len(samples)
    out: dict[str, Any] = {"samples": n, "epsilon": eps, "policies": {}}
    if n == 0:
        return out
    naive_hits = sum(1 for s in samples if s["chosen"] == s["shown"])
    out["logged_hit_rate"] = round(naive_hits / n, 4)
    for name, key in (("engine", "engine"), ("personalized", "greedy")):
        ws: list[float] = []
        rws: list[float] = []
        matched = 0
        for s in samples:
            shown = s["shown"]
            pi = float((s.get("propensities") or {}).get(shown, 0.0))
            p_b = (1.0 - eps) * (1.0 if shown == s["greedy"] else 0.0) + eps * pi
            if p_b <= 0:
                continue
            w = (1.0 / p_b) if s[key] == shown else 0.0
            r = 1.0 if s["chosen"] == shown else 0.0
            ws.append(w)
            rws.append(r * w)
            matched += int(w > 0)
        sw = sum(ws)
        sw2 = sum(w * w for w in ws)
        out["policies"][name] = {
            "matched": matched, "ips": round(sum(rws) / n, 4), "snips": (round(sum(rws) / sw, 4) if sw > 0 else None),
            "ess": (round(sw * sw / sw2, 1) if sw2 > 0 else 0.0),
        }
    return out


async def ips(db: AsyncSession, days: int, epsilon: float) -> dict[str, Any]:
    start, _ = window(days)
    reqs = (await db.execute(select(RouteRequest.id, RouteRequest.propensities, RouteRequest.explored)
                             .where(RouteRequest.created_at >= start, RouteRequest.personalized.is_(True), RouteRequest.status == "ok"))).all()
    if not reqs:
        return {**ips_from_samples([], epsilon), "note": "개인화가 적용된 검색이 아직 없습니다"}
    ids = [r.id for r in reqs]
    choices = {c.request_id: c for c in (await db.execute(select(RouteChoice).where(RouteChoice.request_id.in_(ids)))).scalars().all()}
    results = (await db.execute(select(RouteResult.request_id, RouteResult.rank, RouteResult.engine_rank, RouteResult.payload)
                                .where(RouteResult.request_id.in_(ids)))).all()
    by_req: dict[uuid.UUID, list] = defaultdict(list)
    for r in results:
        by_req[r.request_id].append(r)
    samples: list[dict[str, Any]] = []
    for req in reqs:
        choice = choices.get(req.id)
        rows = by_req.get(req.id) or []
        if choice is None or not rows or not req.propensities:
            continue
        shown = next((r.payload.get("id") for r in rows if r.rank == 1), None)
        engine = next((r.payload.get("id") for r in rows if (r.engine_rank or r.rank) == 1), None)
        greedy = max(req.propensities.items(), key=lambda kv: kv[1])[0]
        if shown is None or engine is None:
            continue
        samples.append({"shown": shown, "chosen": choice.route_id, "engine": engine, "greedy": greedy,
                        "propensities": req.propensities, "explored": bool(req.explored)})
    out = ips_from_samples(samples, epsilon)
    out["explored"] = sum(1 for s in samples if s["explored"])
    out["days"] = days
    out["note"] = ("탐험 표본이 없으면 엔진 정책 추정은 개인화 1순위가 엔진 1순위와 같은 검색에만 기댄다. ESS 가 작으면 신뢰하지 않는다."
                   if out["explored"] == 0 else "ε-greedy 로깅 확률로 보정한 추정. ESS 가 표본 수에 가까울수록 믿을 만하다.")
    return out
