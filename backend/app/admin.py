"""관리자 인증: ADMIN_PASSWORD 하나로 로그인, 별도 JWT 쿠키(`pf_admin`) 세션.

소셜 로그인과 무관하게 동작한다. 비밀번호가 비어 있으면 관리자 기능 전체가 꺼진다(404).
같은 IP 에서 `admin_login_max_failures` 회 실패하면 `admin_login_lockout_s` 초 동안 잠근다.
"""
from __future__ import annotations

import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException, Request

from .config import Settings

ADMIN_COOKIE = "pf_admin"

# ip -> (실패 횟수, 마지막 실패 시각)
_failures: dict[str, tuple[int, float]] = {}


def enabled(cfg: Settings) -> bool:
    return bool(cfg.admin_password)


def issue_session(cfg: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {"role": "admin", "iat": int(now.timestamp()), "exp": int((now + timedelta(hours=cfg.admin_session_hours)).timestamp()),
               "jti": secrets.token_urlsafe(8)}
    return jwt.encode(payload, cfg.jwt_secret, algorithm="HS256")


def read_session(cfg: Settings, token: str | None) -> bool:
    if not token:
        return False
    try:
        payload = jwt.decode(token, cfg.jwt_secret, algorithms=["HS256"])
        return payload.get("role") == "admin"
    except jwt.PyJWTError:
        return False


def is_admin(request: Request) -> bool:
    cfg: Settings = request.app.state.settings
    return enabled(cfg) and read_session(cfg, request.cookies.get(ADMIN_COOKIE))


def require_admin(request: Request) -> None:
    """관리자 엔드포인트 의존성. 기능이 꺼져 있으면 404, 세션이 없으면 401."""
    cfg: Settings = request.app.state.settings
    if not enabled(cfg):
        raise HTTPException(status_code=404, detail="Not Found")
    if not read_session(cfg, request.cookies.get(ADMIN_COOKIE)):
        raise HTTPException(status_code=401, detail="관리자 로그인이 필요합니다")


def locked_for(cfg: Settings, ip: str, now: float | None = None) -> int:
    """잠금이 남아 있으면 남은 초, 아니면 0."""
    now = now or time.time()
    count, last = _failures.get(ip, (0, 0.0))
    if count >= cfg.admin_login_max_failures and now - last < cfg.admin_login_lockout_s:
        return int(cfg.admin_login_lockout_s - (now - last))
    return 0


def check_password(cfg: Settings, ip: str, password: str, now: float | None = None) -> bool:
    now = now or time.time()
    ok = secrets.compare_digest(password.encode("utf-8"), cfg.admin_password.encode("utf-8"))
    if ok:
        _failures.pop(ip, None)
        return True
    count, last = _failures.get(ip, (0, 0.0))
    if now - last > cfg.admin_login_lockout_s:
        count = 0
    _failures[ip] = (count + 1, now)
    return False


def reset_failures() -> None:
    _failures.clear()


def cookie_kwargs(cfg: Settings) -> dict[str, Any]:
    return {"httponly": True, "samesite": "lax", "secure": cfg.cookie_secure, "path": "/", "max_age": cfg.admin_session_hours * 3600}
