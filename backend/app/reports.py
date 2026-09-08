"""시설 제보 API.

사용자(게스트 포함)가 "이 엘리베이터 고장", "여기 계단 있음" 같은 제보를 보내면 `reports` 에 쌓인다.
관리자가 검토해 승인하면 엔진의 가장 가까운 엣지에 `edge_overrides` 가 만들어지고, 이후 모든 검색에 전달되어
경로 계산에 바로 반영된다. 승인·거절·해제는 `admin_routers` 의 `/api/admin/reports*` 에 있다.
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from . import audit, auth
from .config import Settings
from .models import Report, RouteRequest, User

router = APIRouter(prefix="/api", tags=["reports"])

ReportKind = Literal["elevator_broken", "stairs", "kerb", "blocked", "ok", "other"]
KIND_LABELS = {"elevator_broken": "엘리베이터 고장", "stairs": "계단 있음", "kerb": "턱 있음", "blocked": "통행 불가", "ok": "문제 없음(정보 정정)",
               "other": "기타"}

_recent: dict[str, deque[float]] = defaultdict(deque)


MAX_TRACKED_IPS = 5000


def rate_limited(ip: str, limit: int, now: float | None = None) -> bool:
    now = now or time.time()
    if len(_recent) > MAX_TRACKED_IPS:
        for k in [k for k, dq in _recent.items() if not dq or now - dq[-1] > 3600]:
            _recent.pop(k, None)
    q = _recent[ip]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def reset_rate_limits() -> None:
    _recent.clear()


class ReportIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    kind: ReportKind
    note: str = Field(default="", max_length=500)
    place_name: str = Field(default="", max_length=200)
    request_id: str | None = None


class ReportOut(BaseModel):
    id: str
    status: str
    kind: str
    kind_label: str
    created_at: str


def report_out(r: Report) -> dict:
    return {
        "id": str(r.id), "created_at": (r.created_at.replace(tzinfo=timezone.utc) if r.created_at and r.created_at.tzinfo is None else r.created_at).isoformat(),
        "user_id": (str(r.user_id) if r.user_id else None), "request_id": (str(r.request_id) if r.request_id else None),
        "lat": r.lat, "lng": r.lng, "kind": r.kind, "kind_label": KIND_LABELS.get(r.kind, r.kind), "note": r.note, "place_name": r.place_name,
        "status": r.status, "edge_id": r.edge_id, "edge_kind": r.edge_kind, "admin_note": r.admin_note,
        "resolved_at": (r.resolved_at.isoformat() if r.resolved_at else None),
    }


def _settings(request: Request) -> Settings:
    return request.app.state.settings


async def _db(request: Request):
    async for s in request.app.state.db.session():
        yield s


@router.get("/reports/kinds", summary="제보 종류")
async def report_kinds() -> list[dict]:
    return [{"kind": k, "label": v} for k, v in KIND_LABELS.items()]


@router.post("/reports", response_model=ReportOut, status_code=201, summary="시설 제보 (게스트 가능, IP 당 시간당 한도)")
async def create_report(body: ReportIn, request: Request, cfg: Settings = Depends(_settings), db: AsyncSession = Depends(_db)) -> ReportOut:
    ip = audit.client_ip(request)
    if rate_limited(ip, cfg.report_rate_limit_per_hour):
        raise HTTPException(status_code=429, detail="제보가 너무 많습니다. 잠시 후 다시 시도해 주세요")
    user: User | None = await auth.current_user(request, db)
    rid: uuid.UUID | None = None
    if body.request_id:
        try:
            rid = uuid.UUID(body.request_id)
        except ValueError:
            rid = None
        if rid is not None and await db.get(RouteRequest, rid) is None:
            rid = None   # 지워졌거나 잘못된 요청 id 는 FK 위반 대신 비워 둔다
    r = Report(user_id=(user.id if user else None), request_id=rid, lat=body.lat, lng=body.lng, kind=body.kind, note=body.note.strip(),
               place_name=body.place_name.strip(), ip=ip)
    db.add(r)
    await db.commit()
    await db.refresh(r)
    audit.mark(request, "api", f"report:{body.kind}", (user.id if user else None))
    return ReportOut(id=str(r.id), status=r.status, kind=r.kind, kind_label=KIND_LABELS[r.kind],
                     created_at=((r.created_at.replace(tzinfo=timezone.utc) if r.created_at and r.created_at.tzinfo is None else r.created_at) or datetime.now(timezone.utc)).isoformat())


@router.get("/reports/mine", summary="내 제보 (로그인 사용자)")
async def my_reports(request: Request, db: AsyncSession = Depends(_db)) -> list[dict]:
    from sqlalchemy import select

    user = await auth.current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    rows = (await db.execute(select(Report).where(Report.user_id == user.id).order_by(Report.created_at.desc()).limit(50))).scalars().all()
    return [report_out(r) for r in rows]
