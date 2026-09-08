"""API 접근 로그. 모든 /api 요청을 한 행씩 `api_access_logs` 에 남긴다.

핸들러가 `request.state.audit = (kind, detail, user_id)` 를 채우면(로그인·로그아웃·관리자 로그인 등)
그 값이 같은 행에 들어간다. 요청 1건 = 행 1개.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request

from . import auth
from .models import ApiAccessLog

log = logging.getLogger("backend.audit")

# 타일·그늘은 지도를 움직일 때마다 호출되므로 접근 로그에서 뺀다
SKIP_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc", "/api/tiles", "/api/shade")


def mark(request: Request, kind: str, detail: str, user_id: uuid.UUID | None = None) -> None:
    """핸들러에서 인증·관리자 이벤트를 표시한다."""
    request.state.audit = (kind, detail, user_id)


def client_ip(request: Request) -> str:
    # nginx/Caddy 는 자기 앞의 주소를 목록 끝에 붙인다. 첫 항목은 클라이언트가 마음대로 넣을 수 있으니 마지막 항목을 쓴다
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[-1].strip()[:64]
    return (request.client.host if request.client else "")[:64]


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def access_log(request: Request, call_next: Any):
        path = request.url.path
        cfg = getattr(request.app.state, "settings", None)
        if cfg is None or not cfg.access_log_enabled or not path.startswith("/api") or path.startswith(SKIP_PREFIXES):
            return await call_next(request)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration = round((time.perf_counter() - started) * 1000, 1)
            try:
                await _write(request, status, duration)
            except Exception:  # noqa: BLE001  로그 실패가 응답을 막지 않는다
                log.exception("접근 로그 기록 실패")


async def _write(request: Request, status: int, duration_ms: float) -> None:
    cfg = request.app.state.settings
    audit = getattr(request.state, "audit", None)
    kind, detail, user_id = ("api", None, None)
    if audit:
        kind, detail, user_id = audit
    elif request.url.path.startswith("/api/admin"):
        kind = "admin"
    if user_id is None:
        user_id = auth.read_session(cfg, request.cookies.get(auth.SESSION_COOKIE))
    row = ApiAccessLog(kind=kind, method=request.method[:8], path=request.url.path[:200], status=int(status), duration_ms=duration_ms,
                       user_id=user_id, ip=client_ip(request), user_agent=(request.headers.get("user-agent") or "")[:300],
                       detail=(detail[:2000] if detail else None), request_id=str(getattr(request.state, "request_id", ""))[:64])
    async for db in request.app.state.db.session():
        db.add(row)
        await db.commit()
