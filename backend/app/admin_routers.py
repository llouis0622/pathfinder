"""관리자 API (/api/admin). 모든 조회는 `pf_admin` 세션 쿠키가 필요하다."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from . import admin, audit
from .config import Settings
from .models import (
    ApiAccessLog,
    EdgeOverride,
    EngineRun,
    PlaceSearch,
    PolicyUpdate,
    Report,
    RouteChoice,
    RouteRequest,
    RouteResult,
    User,
    UserPolicy,
)
from .reports import KIND_LABELS, report_out
from .services import admin_stats as stats
from .services import engine_client
from .services.maintenance import log_counts, prune_logs
from .services.personalization import Policy

KST = ZoneInfo("Asia/Seoul")
EXPORT_LIMIT = 50_000

router = APIRouter(prefix="/api/admin", tags=["admin"])
guarded = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(admin.require_admin)])


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_db(request: Request):
    async for s in request.app.state.db.session():
        yield s


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="id 형식이 올바르지 않습니다") from exc


def _date(value: str | None, end: bool = False) -> datetime | None:
    """YYYY-MM-DD (KST) → UTC. end=True 면 그날 끝."""
    if not value:
        return None
    try:
        d = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=KST)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="날짜는 YYYY-MM-DD 형식이어야 합니다") from exc
    if end:
        d += timedelta(days=1)
    return d.astimezone(timezone.utc)


class Page(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=50, ge=1, le=200)


def page_params(page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200)) -> Page:
    return Page(page=page, size=size)


async def paginate(db: AsyncSession, stmt: Select, pg: Page) -> tuple[list, int]:
    total = int((await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one())
    rows = (await db.execute(stmt.offset((pg.page - 1) * pg.size).limit(pg.size))).all()
    return rows, total


def envelope(items: list, total: int, pg: Page) -> dict:
    return {"items": items, "total": total, "page": pg.page, "size": pg.size, "pages": max(1, -(-total // pg.size))}


# ---------------------------------------------------------------- 인증
class LoginBody(BaseModel):
    password: str = Field(min_length=1, max_length=200)


@router.get("/me", summary="관리자 세션 상태")
async def admin_me(request: Request, cfg: Settings = Depends(get_settings)) -> dict:
    return {"configured": admin.enabled(cfg), "admin": admin.is_admin(request)}


@router.post("/login", summary="관리자 로그인 (ADMIN_PASSWORD)")
async def admin_login(body: LoginBody, request: Request, response: Response, cfg: Settings = Depends(get_settings)) -> dict:
    if not admin.enabled(cfg):
        raise HTTPException(status_code=404, detail="Not Found")
    ip = audit.client_ip(request)
    remaining = admin.locked_for(cfg, ip)
    if remaining:
        audit.mark(request, "admin", "login_locked")
        raise HTTPException(status_code=429, detail=f"로그인 시도가 너무 많습니다. {remaining}초 후 다시 시도하세요")
    if not admin.check_password(cfg, ip, body.password):
        audit.mark(request, "admin", "login_failed")
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다")
    audit.mark(request, "admin", "login")
    response.set_cookie(admin.ADMIN_COOKIE, admin.issue_session(cfg), **admin.cookie_kwargs(cfg))
    return {"admin": True}


@router.post("/logout", summary="관리자 로그아웃")
async def admin_logout(request: Request, response: Response) -> dict:
    audit.mark(request, "admin", "logout")
    response.delete_cookie(admin.ADMIN_COOKIE, path="/")
    return {"admin": False}


# ---------------------------------------------------------------- 대시보드·분석
@guarded.get("/overview", summary="대시보드 KPI·추이·최근 활동")
async def overview(db: AsyncSession = Depends(get_db)) -> dict:
    return await stats.overview(db)


@guarded.get("/analytics/usage", summary="이용 추이")
async def analytics_usage(days: int = Query(30, ge=1, le=365), db: AsyncSession = Depends(get_db)) -> dict:
    return await stats.usage(db, days)


@guarded.get("/analytics/quality", summary="경로 품질·선택률")
async def analytics_quality(days: int = Query(30, ge=1, le=365), db: AsyncSession = Depends(get_db)) -> dict:
    return await stats.quality(db, days)


@guarded.get("/analytics/spatial", summary="공간 분석 (인기 출발·도착·역)")
async def analytics_spatial(days: int = Query(30, ge=1, le=365), db: AsyncSession = Depends(get_db)) -> dict:
    return await stats.spatial(db, days)


@guarded.get("/analytics/engine", summary="엔진 성능 집계")
async def analytics_engine(days: int = Query(30, ge=1, le=365), db: AsyncSession = Depends(get_db)) -> dict:
    return await stats.engine_stats(db, days)


@guarded.get("/preferences", summary="학습된 취향 분포와 사용자별 가중치")
async def preferences(db: AsyncSession = Depends(get_db)) -> dict:
    return await stats.preferences(db)


# ---------------------------------------------------------------- 로그
@guarded.get("/logs/requests", summary="경로 검색 요청 로그")
async def log_requests(pg: Page = Depends(page_params), profile: str | None = Query(None), status: str | None = Query(None),
                       user_id: str | None = Query(None), q: str | None = Query(None, max_length=100),
                       date_from: str | None = Query(None, alias="from"), date_to: str | None = Query(None, alias="to"),
                       personalized: bool | None = Query(None), db: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(RouteRequest).order_by(RouteRequest.created_at.desc())
    if profile:
        stmt = stmt.where(RouteRequest.profile == profile)
    if status:
        stmt = stmt.where(RouteRequest.status == status)
    if user_id:
        stmt = stmt.where(RouteRequest.user_id == _uuid(user_id))
    if personalized is not None:
        stmt = stmt.where(RouteRequest.personalized == personalized)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(RouteRequest.origin_name.ilike(like), RouteRequest.dest_name.ilike(like)))
    if (start := _date(date_from)) is not None:
        stmt = stmt.where(RouteRequest.created_at >= start)
    if (end := _date(date_to, end=True)) is not None:
        stmt = stmt.where(RouteRequest.created_at < end)
    rows, total = await paginate(db, stmt, pg)
    reqs = [r[0] for r in rows]
    users = await stats.users_by_id(db, {r.user_id for r in reqs if r.user_id})
    chosen = await stats.choices_by_request(db, [r.id for r in reqs])
    counts: dict[uuid.UUID, int] = {}
    if reqs:
        cnt = (await db.execute(select(RouteResult.request_id, func.count(RouteResult.id)).where(RouteResult.request_id.in_([r.id for r in reqs]))
                                .group_by(RouteResult.request_id))).all()
        counts = {rid: int(n) for rid, n in cnt}
    items = [stats.request_row(r, users.get(r.user_id), counts.get(r.id, 0), (chosen[r.id].shown_rank if r.id in chosen else None)) for r in reqs]
    return envelope(items, total, pg)


@guarded.get("/logs/requests/{request_id}", summary="경로 검색 요청 상세 (결과·선택·엔진·정책 갱신)")
async def log_request_detail(request_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    rid = _uuid(request_id)
    record = (await db.execute(select(RouteRequest).where(RouteRequest.id == rid).options(selectinload(RouteRequest.results)))).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    user = await db.get(User, record.user_id) if record.user_id else None
    choice = (await db.execute(select(RouteChoice).where(RouteChoice.request_id == rid).order_by(RouteChoice.created_at.desc()))).scalars().first()
    run = (await db.execute(select(EngineRun).where(EngineRun.request_id == rid))).scalars().first()
    update = (await db.execute(select(PolicyUpdate).where(PolicyUpdate.request_id == rid))).scalars().first()
    results = sorted(record.results, key=lambda r: r.rank)
    return {
        "request": stats.request_row(record, user, len(results), (choice.shown_rank if choice else None)),
        "weather": record.weather, "options": record.options, "propensities": record.propensities, "metadata": record.engine_metadata,
        "routes": [{"rank": r.rank, "engine_rank": r.engine_rank, "summary": r.summary, "badges": r.badges or [], "cautions": r.cautions or [],
                    "total_duration_min": r.total_duration_min, "walk_distance_m": r.walk_distance_m, "transfers": r.transfers,
                    "generalized_cost_s": r.generalized_cost_s, "payload": r.payload} for r in results],
        "choice": (stats.choice_row(choice, record, user) if choice else None),
        "engine_run": (stats.engine_row(run, record) if run else None),
        "policy_update": (stats.policy_update_row(update) if update else None),
    }


@guarded.get("/logs/access", summary="API 접근·인증 로그")
async def log_access(pg: Page = Depends(page_params), kind: str | None = Query(None), path: str | None = Query(None, max_length=200),
                     status_min: int | None = Query(None, ge=100, le=599), user_id: str | None = Query(None),
                     date_from: str | None = Query(None, alias="from"), date_to: str | None = Query(None, alias="to"),
                     db: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(ApiAccessLog).order_by(ApiAccessLog.created_at.desc())
    if kind:
        stmt = stmt.where(ApiAccessLog.kind == kind)
    if path:
        stmt = stmt.where(ApiAccessLog.path.like(f"{path}%"))
    if status_min is not None:
        stmt = stmt.where(ApiAccessLog.status >= status_min)
    if user_id:
        stmt = stmt.where(ApiAccessLog.user_id == _uuid(user_id))
    if (start := _date(date_from)) is not None:
        stmt = stmt.where(ApiAccessLog.created_at >= start)
    if (end := _date(date_to, end=True)) is not None:
        stmt = stmt.where(ApiAccessLog.created_at < end)
    rows, total = await paginate(db, stmt, pg)
    logs = [r[0] for r in rows]
    users = await stats.users_by_id(db, {a.user_id for a in logs if a.user_id})
    return envelope([stats.access_row(a, users.get(a.user_id)) for a in logs], total, pg)


@guarded.get("/logs/engine", summary="엔진 성능 로그")
async def log_engine(pg: Page = Depends(page_params), profile: str | None = Query(None),
                     date_from: str | None = Query(None, alias="from"), date_to: str | None = Query(None, alias="to"),
                     db: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(EngineRun, RouteRequest).join(RouteRequest, RouteRequest.id == EngineRun.request_id).order_by(EngineRun.created_at.desc())
    if profile:
        stmt = stmt.where(EngineRun.profile == profile)
    if (start := _date(date_from)) is not None:
        stmt = stmt.where(EngineRun.created_at >= start)
    if (end := _date(date_to, end=True)) is not None:
        stmt = stmt.where(EngineRun.created_at < end)
    rows, total = await paginate(db, stmt, pg)
    return envelope([stats.engine_row(run, req) for run, req in rows], total, pg)


@guarded.get("/logs/choices", summary="경로 선택 로그")
async def log_choices(pg: Page = Depends(page_params), user_id: str | None = Query(None), learned: bool | None = Query(None),
                      db: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(RouteChoice, RouteRequest).join(RouteRequest, RouteRequest.id == RouteChoice.request_id).order_by(RouteChoice.created_at.desc())
    if user_id:
        stmt = stmt.where(RouteChoice.user_id == _uuid(user_id))
    if learned is not None:
        stmt = stmt.where(RouteChoice.learned == learned)
    rows, total = await paginate(db, stmt, pg)
    users = await stats.users_by_id(db, {c.user_id for c, _ in rows if c.user_id})
    return envelope([stats.choice_row(c, req, users.get(c.user_id)) for c, req in rows], total, pg)


@guarded.get("/logs/policy-updates", summary="개인화 정책 갱신 이력")
async def log_policy_updates(pg: Page = Depends(page_params), user_id: str | None = Query(None), db: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(PolicyUpdate).order_by(PolicyUpdate.created_at.desc())
    if user_id:
        stmt = stmt.where(PolicyUpdate.user_id == _uuid(user_id))
    rows, total = await paginate(db, stmt, pg)
    return envelope([stats.policy_update_row(p[0]) for p in rows], total, pg)


@guarded.get("/logs/places", summary="장소 검색 로그")
async def log_places(pg: Page = Depends(page_params), q: str | None = Query(None, max_length=100), db: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(PlaceSearch).order_by(PlaceSearch.created_at.desc())
    if q:
        stmt = stmt.where(PlaceSearch.query.ilike(f"%{q}%"))
    rows, total = await paginate(db, stmt, pg)
    items = [{"id": str(p.id), "created_at": stats.iso(p.created_at), "query": p.query, "source": p.source, "result_count": p.result_count}
             for (p,) in rows]
    return envelope(items, total, pg)


# ---------------------------------------------------------------- 사용자
@guarded.get("/users", summary="사용자 목록 (활동 통계 포함)")
async def users_list(pg: Page = Depends(page_params), q: str | None = Query(None, max_length=100), provider: str | None = Query(None),
                     sort: str = Query("last_login", pattern="^(last_login|created|requests|choices|updates)$"),
                     db: AsyncSession = Depends(get_db)) -> dict:
    req_cnt = select(RouteRequest.user_id, func.count(RouteRequest.id).label("n")).group_by(RouteRequest.user_id).subquery()
    ch_cnt = select(RouteChoice.user_id, func.count(RouteChoice.id).label("n")).group_by(RouteChoice.user_id).subquery()
    stmt = (select(User, func.coalesce(req_cnt.c.n, 0), func.coalesce(ch_cnt.c.n, 0), func.coalesce(UserPolicy.updates, 0), UserPolicy.policy)
            .outerjoin(req_cnt, req_cnt.c.user_id == User.id).outerjoin(ch_cnt, ch_cnt.c.user_id == User.id)
            .outerjoin(UserPolicy, UserPolicy.user_id == User.id))
    if q:
        stmt = stmt.where(User.nickname.ilike(f"%{q}%"))
    if provider:
        stmt = stmt.where(User.provider == provider)
    order = {"last_login": User.last_login_at.desc().nullslast(), "created": User.created_at.desc(),
             "requests": func.coalesce(req_cnt.c.n, 0).desc(), "choices": func.coalesce(ch_cnt.c.n, 0).desc(),
             "updates": func.coalesce(UserPolicy.updates, 0).desc()}[sort]
    stmt = stmt.order_by(order, User.created_at.desc())
    rows, total = await paginate(db, stmt, pg)
    items = []
    for u, n_req, n_ch, updates, policy in rows:
        summary = Policy.from_dict(policy).summary() if policy else []
        items.append({**stats.user_out(u), "requests": int(n_req), "choices": int(n_ch), "updates": int(updates), "summary": summary})
    providers = (await db.execute(select(User.provider, func.count(User.id)).group_by(User.provider))).all()
    return {**envelope(items, total, pg), "providers": [{"provider": p, "count": int(n)} for p, n in providers]}


@guarded.get("/users/{user_id}", summary="사용자 상세 (취향·요청·선택·정책 이력)")
async def user_detail(user_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    uid = _uuid(user_id)
    user = await db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    policy_row = await db.get(UserPolicy, uid)
    policy = Policy.from_dict(policy_row.policy) if policy_row else Policy()
    reqs = (await db.execute(select(RouteRequest).where(RouteRequest.user_id == uid).order_by(RouteRequest.created_at.desc()).limit(20))).scalars().all()
    chosen = await stats.choices_by_request(db, [r.id for r in reqs])
    choices = (await db.execute(select(RouteChoice, RouteRequest).join(RouteRequest, RouteRequest.id == RouteChoice.request_id)
                                .where(RouteChoice.user_id == uid).order_by(RouteChoice.created_at.desc()).limit(50))).all()
    updates = (await db.execute(select(PolicyUpdate).where(PolicyUpdate.user_id == uid).order_by(PolicyUpdate.created_at))).scalars().all()
    n_req = int((await db.execute(select(func.count(RouteRequest.id)).where(RouteRequest.user_id == uid))).scalar_one())
    n_ch = int((await db.execute(select(func.count(RouteChoice.id)).where(RouteChoice.user_id == uid))).scalar_one())
    n_pers = int((await db.execute(select(func.count(RouteRequest.id)).where(RouteRequest.user_id == uid, RouteRequest.personalized.is_(True)))).scalar_one())
    last_access = (await db.execute(select(ApiAccessLog).where(ApiAccessLog.user_id == uid).order_by(ApiAccessLog.created_at.desc()).limit(10))).scalars().all()
    profiles = (await db.execute(select(RouteRequest.profile, func.count(RouteRequest.id)).where(RouteRequest.user_id == uid)
                                 .group_by(RouteRequest.profile))).all()
    return {
        "user": stats.user_out(user),
        "stats": {"requests": n_req, "choices": n_ch, "personalized_requests": n_pers, "policy_updates": len(updates),
                  "rank1_choice_rate": stats.rate(sum(1 for c, _ in choices if c.shown_rank == 1), len(choices)),
                  "profiles": [{"profile": p, "label": stats.PROFILE_LABELS.get(p, p), "count": int(n)} for p, n in profiles]},
        "policy": {**stats.policy_out(policy), "updated_at": (stats.iso(policy_row.updated_at) if policy_row else None)},
        "recent_requests": [stats.request_row(r, user, None, (chosen[r.id].shown_rank if r.id in chosen else None)) for r in reqs],
        "choices": [stats.choice_row(c, req, user) for c, req in choices],
        "policy_history": [stats.policy_update_row(p) for p in updates],
        "recent_access": [stats.access_row(a, user) for a in last_access],
    }


@guarded.delete("/users/{user_id}/policy", summary="사용자 취향(정책) 초기화")
async def user_reset_policy(user_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    uid = _uuid(user_id)
    row = await db.get(UserPolicy, uid)
    if row is not None:
        await db.delete(row)
        await db.commit()
    audit.mark(request, "admin", f"reset_policy:{uid}")
    return {"ok": True, "reset": row is not None}


# ---------------------------------------------------------------- 로그 정리
class PruneBody(BaseModel):
    days: int | None = Field(default=None, ge=0, le=3650, description="이 일수보다 오래된 로그 삭제. 0 이면 전부. 생략 시 LOG_RETENTION_DAYS")


@guarded.get("/maintenance", summary="로그 보존 설정과 표별 행 수")
async def maintenance_info(cfg: Settings = Depends(get_settings), db: AsyncSession = Depends(get_db)) -> dict:
    return {"retention_days": cfg.log_retention_days, "tables": await log_counts(db)}


@guarded.post("/maintenance/prune", summary="오래된 접근·장소검색·엔진 로그 즉시 정리")
async def maintenance_prune(body: PruneBody, request: Request, cfg: Settings = Depends(get_settings), db: AsyncSession = Depends(get_db)) -> dict:
    days = cfg.log_retention_days if body.days is None else body.days
    deleted = await prune_logs(db, days)
    audit.mark(request, "admin", f"prune_logs:{days}d:{sum(deleted.values())}")
    return {"days": days, "deleted": deleted}


@guarded.get("/analytics/ips", summary="개인화 오프라인 평가 (IPS / SNIPS)")
async def analytics_ips(days: int = Query(30, ge=1, le=365), cfg: Settings = Depends(get_settings), db: AsyncSession = Depends(get_db)) -> dict:
    return await stats.ips(db, days, cfg.personalization_epsilon)


# ---------------------------------------------------------------- 시설 제보 검토·오버라이드
OVERRIDE_KINDS = ("elevator_broken", "stairs", "kerb", "blocked", "ok")


def override_out(o: EdgeOverride) -> dict:
    return {"id": str(o.id), "created_at": stats.iso(o.created_at), "edge_id": o.edge_id, "kind": o.kind, "kind_label": KIND_LABELS.get(o.kind, o.kind),
            "active": o.active, "expires_at": stats.iso(o.expires_at), "note": o.note, "report_id": (str(o.report_id) if o.report_id else None),
            "deactivated_at": stats.iso(o.deactivated_at)}


def _clear_search_cache(request: Request) -> None:
    cache = getattr(request.app.state, "search_cache", None)
    if cache is not None:
        cache.clear()


@guarded.get("/reports", summary="시설 제보 목록")
async def admin_reports(pg: Page = Depends(page_params), status: str | None = Query(None), kind: str | None = Query(None),
                        db: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(Report).order_by(Report.created_at.desc())
    if status:
        stmt = stmt.where(Report.status == status)
    if kind:
        stmt = stmt.where(Report.kind == kind)
    rows, total = await paginate(db, stmt, pg)
    reports = [r[0] for r in rows]
    users = await stats.users_by_id(db, {r.user_id for r in reports if r.user_id})
    items = [{**report_out(r), "user": stats.user_out(users.get(r.user_id))} for r in reports]
    counts = (await db.execute(select(Report.status, func.count(Report.id)).group_by(Report.status))).all()
    return {**envelope(items, total, pg), "counts": {s: int(n) for s, n in counts}, "kinds": KIND_LABELS}


class AcceptBody(BaseModel):
    edge_id: int | None = Field(default=None, description="비우면 제보 좌표에서 가장 가까운 엣지를 엔진에 묻는다")
    kind: str | None = Field(default=None, description="비우면 제보 종류 그대로 (other 는 반드시 지정)")
    expires_days: int | None = Field(default=None, ge=1, le=3650)
    note: str = Field(default="", max_length=500)


@guarded.post("/reports/{report_id}/accept", summary="제보 승인 → 엣지 오버라이드 생성 (검색에 즉시 반영)")
async def accept_report(report_id: str, body: AcceptBody, request: Request, cfg: Settings = Depends(get_settings),
                        db: AsyncSession = Depends(get_db)) -> dict:
    r = await db.get(Report, _uuid(report_id))
    if r is None:
        raise HTTPException(status_code=404, detail="제보를 찾을 수 없습니다")
    kind = body.kind or r.kind
    if kind not in OVERRIDE_KINDS:
        raise HTTPException(status_code=422, detail="오버라이드 종류를 지정하세요 (elevator_broken·stairs·kerb·blocked·ok)")
    edge_id = body.edge_id
    edge_kind = ""
    if edge_id is None:
        try:
            near = await engine_client.nearest_edge(cfg, r.lat, r.lng)
        except engine_client.EngineError as exc:
            raise HTTPException(status_code=exc.status if exc.status in (422, 503) else 502, detail=exc.detail) from exc
        edge_id = int(near["edge_id"])
        edge_kind = str(near.get("kind", ""))
    now = datetime.now(timezone.utc)
    ov = EdgeOverride(edge_id=edge_id, kind=kind, active=True, note=body.note, report_id=r.id,
                      expires_at=(now + timedelta(days=body.expires_days) if body.expires_days else None))
    db.add(ov)
    r.status = "accepted"
    r.edge_id = edge_id
    r.edge_kind = edge_kind
    r.admin_note = body.note
    r.resolved_at = now
    await db.commit()
    await db.refresh(ov)
    _clear_search_cache(request)
    audit.mark(request, "admin", f"report_accept:{r.id}:{kind}:{edge_id}")
    return {"report": report_out(r), "override": override_out(ov)}


class RejectBody(BaseModel):
    note: str = Field(default="", max_length=500)


@guarded.post("/reports/{report_id}/reject", summary="제보 거절")
async def reject_report(report_id: str, body: RejectBody, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    r = await db.get(Report, _uuid(report_id))
    if r is None:
        raise HTTPException(status_code=404, detail="제보를 찾을 수 없습니다")
    r.status = "rejected"
    r.admin_note = body.note
    r.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    audit.mark(request, "admin", f"report_reject:{r.id}")
    return report_out(r)


@guarded.get("/overrides", summary="엣지 오버라이드 목록")
async def admin_overrides(pg: Page = Depends(page_params), active: bool | None = Query(None), db: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(EdgeOverride).order_by(EdgeOverride.created_at.desc())
    if active is not None:
        stmt = stmt.where(EdgeOverride.active == active)
    rows, total = await paginate(db, stmt, pg)
    return envelope([override_out(o[0]) for o in rows], total, pg)


class OverrideBody(BaseModel):
    edge_id: int
    kind: str
    expires_days: int | None = Field(default=None, ge=1, le=3650)
    note: str = Field(default="", max_length=500)


@guarded.post("/overrides", summary="오버라이드 직접 추가 (제보 없이)")
async def create_override(body: OverrideBody, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    if body.kind not in OVERRIDE_KINDS:
        raise HTTPException(status_code=422, detail="종류는 elevator_broken·stairs·kerb·blocked·ok 중 하나")
    now = datetime.now(timezone.utc)
    ov = EdgeOverride(edge_id=body.edge_id, kind=body.kind, active=True, note=body.note,
                      expires_at=(now + timedelta(days=body.expires_days) if body.expires_days else None))
    db.add(ov)
    await db.commit()
    await db.refresh(ov)
    _clear_search_cache(request)
    audit.mark(request, "admin", f"override_add:{body.kind}:{body.edge_id}")
    return override_out(ov)


@guarded.delete("/overrides/{override_id}", summary="오버라이드 해제")
async def deactivate_override(override_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    ov = await db.get(EdgeOverride, _uuid(override_id))
    if ov is None:
        raise HTTPException(status_code=404, detail="오버라이드를 찾을 수 없습니다")
    ov.active = False
    ov.deactivated_at = datetime.now(timezone.utc)
    await db.commit()
    _clear_search_cache(request)
    audit.mark(request, "admin", f"override_off:{ov.id}")
    return override_out(ov)


@guarded.get("/data-quality", summary="데이터 품질: 엔진 그래프 통계 + 제보·오버라이드·캐시 상태")
async def data_quality(request: Request, cfg: Settings = Depends(get_settings), db: AsyncSession = Depends(get_db)) -> dict:
    try:
        graph = await engine_client.graph_stats(cfg)
    except engine_client.EngineError as exc:
        graph = {"error": exc.detail}
    report_counts = {s: int(n) for s, n in (await db.execute(select(Report.status, func.count(Report.id)).group_by(Report.status))).all()}
    active = int((await db.execute(select(func.count(EdgeOverride.id)).where(EdgeOverride.active.is_(True)))).scalar_one() or 0)
    cache = getattr(request.app.state, "search_cache", None)
    return {"graph": graph, "reports": report_counts, "active_overrides": active, "search_cache": (cache.stats() if cache else None)}


# ---------------------------------------------------------------- CSV 내보내기
def _csv(rows: list[dict[str, Any]], fields: list[str], name: str) -> StreamingResponse:
    buf = io.StringIO()
    buf.write("﻿")  # 엑셀용 BOM
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if v is None else v) for k, v in r.items()})
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})


@guarded.get("/export/{kind}.csv", summary="CSV 내보내기 (requests | choices | users | access | engine)")
async def export_csv(kind: str, days: int = Query(30, ge=1, le=3650), db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    start, _ = stats.window(days)
    if kind == "requests":
        rows = (await db.execute(select(RouteRequest).where(RouteRequest.created_at >= start).order_by(RouteRequest.created_at.desc())
                                 .limit(EXPORT_LIMIT))).scalars().all()
        data = [{"id": str(r.id), "created_at": stats.iso(r.created_at), "user_id": (str(r.user_id) if r.user_id else ""), "profile": r.profile,
                 "origin_name": r.origin_name, "origin_lat": r.origin_lat, "origin_lng": r.origin_lng, "dest_name": r.dest_name,
                 "dest_lat": r.dest_lat, "dest_lng": r.dest_lng, "status": r.status, "elapsed_ms": r.elapsed_ms,
                 "personalized": r.personalized, "explored": r.explored, "prefer_shade": bool((r.options or {}).get("prefer_shade")),
                 "weather_flags": "|".join((r.weather or {}).get("flags") or []), "error": r.error} for r in rows]
        return _csv(data, list(data[0].keys()) if data else ["id"], f"requests_{days}d")
    if kind == "choices":
        rows = (await db.execute(select(RouteChoice, RouteRequest).join(RouteRequest, RouteRequest.id == RouteChoice.request_id)
                                 .where(RouteChoice.created_at >= start).order_by(RouteChoice.created_at.desc()).limit(EXPORT_LIMIT))).all()
        data = [stats.choice_row(c, req) for c, req in rows]
        for d in data:
            d.pop("user", None)
        return _csv(data, list(data[0].keys()) if data else ["id"], f"choices_{days}d")
    if kind == "users":
        rows = (await db.execute(select(User, UserPolicy).outerjoin(UserPolicy, UserPolicy.user_id == User.id).order_by(User.created_at))).all()
        data = [{**stats.user_out(u), "updates": (p.updates if p else 0), "summary": " / ".join(Policy.from_dict(p.policy).summary() if p else [])}
                for u, p in rows]
        return _csv(data, list(data[0].keys()) if data else ["id"], "users")
    if kind == "access":
        rows = (await db.execute(select(ApiAccessLog).where(ApiAccessLog.created_at >= start).order_by(ApiAccessLog.created_at.desc())
                                 .limit(EXPORT_LIMIT))).scalars().all()
        data = [stats.access_row(a) for a in rows]
        for d in data:
            d.pop("user", None)
        return _csv(data, list(data[0].keys()) if data else ["id"], f"access_{days}d")
    if kind == "engine":
        rows = (await db.execute(select(EngineRun, RouteRequest).join(RouteRequest, RouteRequest.id == EngineRun.request_id)
                                 .where(EngineRun.created_at >= start).order_by(EngineRun.created_at.desc()).limit(EXPORT_LIMIT))).all()
        data = []
        for run, req in rows:
            row = stats.engine_row(run, req)
            aco, ga = row.pop("aco"), row.pop("ga")
            row.update({f"aco_{k}": v for k, v in aco.items()})
            row.update({f"ga_{k}": v for k, v in ga.items()})
            row["weather_flags"] = "|".join(row["weather_flags"])
            data.append(row)
        return _csv(data, list(data[0].keys()) if data else ["id"], f"engine_{days}d")
    raise HTTPException(status_code=404, detail="알 수 없는 내보내기 종류입니다")
