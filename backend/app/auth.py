"""카카오·네이버 OAuth 2.0 로그인과 JWT 세션 쿠키.

흐름: GET /api/auth/{provider}/login → 공급자 동의 화면 → GET /api/auth/{provider}/callback?code&state
     → 토큰 교환 → 프로필 조회 → users upsert → 세션 쿠키 발급 → FRONTEND_URL 로 리다이렉트.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import http
from .config import Settings
from .models import User

log = logging.getLogger("backend.auth")
SESSION_COOKIE = "pf_session"
STATE_COOKIE = "pf_oauth_state"

PROVIDERS: dict[str, dict[str, str]] = {
    "kakao": {
        "authorize": "https://kauth.kakao.com/oauth/authorize",
        "token": "https://kauth.kakao.com/oauth/token",
        "profile": "https://kapi.kakao.com/v2/user/me",
    },
    "naver": {
        "authorize": "https://nid.naver.com/oauth2.0/authorize",
        "token": "https://nid.naver.com/oauth2.0/token",
        "profile": "https://openapi.naver.com/v1/nid/me",
    },
}


@dataclass(frozen=True)
class ProviderProfile:
    provider: str
    provider_user_id: str
    nickname: str
    avatar_url: str


def provider_configured(cfg: Settings, provider: str) -> bool:
    if provider == "kakao":
        return bool(cfg.kakao_client_id)
    if provider == "naver":
        return bool(cfg.naver_client_id and cfg.naver_client_secret)
    return False


def configured_providers(cfg: Settings) -> list[str]:
    return [p for p in PROVIDERS if provider_configured(cfg, p)]


def redirect_uri(cfg: Settings, provider: str) -> str:
    return f"{cfg.public_base_url.rstrip('/')}/api/auth/{provider}/callback"


def authorize_url(cfg: Settings, provider: str, state: str) -> str:
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail="지원하지 않는 로그인 공급자입니다")
    if not provider_configured(cfg, provider):
        raise HTTPException(status_code=503, detail=f"{provider} 로그인이 설정되지 않았습니다")
    client_id = cfg.kakao_client_id if provider == "kakao" else cfg.naver_client_id
    params = {"response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri(cfg, provider), "state": state}
    return str(httpx.URL(PROVIDERS[provider]["authorize"], params=params))


async def exchange_code(cfg: Settings, provider: str, code: str, state: str) -> ProviderProfile:
    p = PROVIDERS[provider]
    if provider == "kakao":
        data = {"grant_type": "authorization_code", "client_id": cfg.kakao_client_id, "redirect_uri": redirect_uri(cfg, provider), "code": code}
        if cfg.kakao_client_secret:
            data["client_secret"] = cfg.kakao_client_secret
    else:
        data = {"grant_type": "authorization_code", "client_id": cfg.naver_client_id, "client_secret": cfg.naver_client_secret, "code": code, "state": state}
    async with http.client(timeout=10.0) as client:
        token_res = await client.post(p["token"], data=data, headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"})
        if token_res.status_code != 200:
            raise HTTPException(status_code=502, detail=f"{provider} 토큰 교환 실패")
        access_token = token_res.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail=f"{provider} 토큰 응답에 access_token 이 없습니다")
        prof_res = await client.get(p["profile"], headers={"Authorization": f"Bearer {access_token}"})
        if prof_res.status_code != 200:
            raise HTTPException(status_code=502, detail=f"{provider} 프로필 조회 실패")
        return parse_profile(provider, prof_res.json())


def parse_profile(provider: str, payload: dict[str, Any]) -> ProviderProfile:
    if provider == "kakao":
        account = payload.get("kakao_account") or {}
        profile = account.get("profile") or payload.get("properties") or {}
        return ProviderProfile("kakao", str(payload.get("id")), str(profile.get("nickname") or "카카오 사용자"),
                               str(profile.get("thumbnail_image_url") or profile.get("thumbnail_image") or ""))
    resp = payload.get("response") or {}
    return ProviderProfile("naver", str(resp.get("id")), str(resp.get("nickname") or resp.get("name") or "네이버 사용자"),
                           str(resp.get("profile_image") or ""))


async def upsert_user(db: AsyncSession, profile: ProviderProfile) -> User:
    stmt = select(User).where(User.provider == profile.provider, User.provider_user_id == profile.provider_user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if user is None:
        user = User(provider=profile.provider, provider_user_id=profile.provider_user_id, nickname=profile.nickname[:100],
                    avatar_url=profile.avatar_url[:500], last_login_at=now)
        db.add(user)
    else:
        user.nickname = profile.nickname[:100] or user.nickname
        user.avatar_url = profile.avatar_url[:500] or user.avatar_url
        user.last_login_at = now
    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------- 세션 (JWT 쿠키)
def issue_session(cfg: Settings, user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user.id), "prv": user.provider, "nick": user.nickname, "iat": int(now.timestamp()),
               "exp": int((now + timedelta(days=cfg.session_days)).timestamp())}
    return jwt.encode(payload, cfg.jwt_secret, algorithm="HS256")


def read_session(cfg: Settings, token: str | None) -> uuid.UUID | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, cfg.jwt_secret, algorithms=["HS256"])
        return uuid.UUID(str(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def new_state() -> str:
    return secrets.token_urlsafe(24)


async def current_user(request: Request, db: AsyncSession) -> User | None:
    cfg: Settings = request.app.state.settings
    user_id = read_session(cfg, request.cookies.get(SESSION_COOKIE))
    if user_id is None:
        return None
    return await db.get(User, user_id)


def cookie_kwargs(cfg: Settings) -> dict[str, Any]:
    return {"httponly": True, "samesite": "lax", "secure": cfg.cookie_secure, "path": "/", "max_age": cfg.session_days * 86400}
