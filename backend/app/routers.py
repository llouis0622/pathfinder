"""백엔드 API 라우터."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from . import auth
from .config import Settings
from .models import PlaceSearch, User
from .schemas import (
    ChooseRequest,
    ChooseResponse,
    PlaceSearchResponse,
    PreferencesOut,
    ProfileOut,
    RouteSearchRequest,
    RouteSearchResponse,
    StoredRouteResponse,
    UserOut,
    WeatherOut,
)
from .services import engine_client
from .services.places import search_places
from .services.route import get_stored, load_policy, record_choice, search_and_store
from .services.weather import get_weather

router = APIRouter(prefix="/api", tags=["backend"])

STATIC_PROFILES = [
    ProfileOut(id="wheelchair", label="휠체어 이용자"), ProfileOut(id="elderly", label="고령자"),
    ProfileOut(id="walking_aid", label="보행보조기·목발 이용자"), ProfileOut(id="visually_impaired", label="시각장애인"),
]


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_db(request: Request):
    async for s in request.app.state.db.session():
        yield s


async def get_user(request: Request, db: AsyncSession = Depends(get_db)) -> User | None:
    return await auth.current_user(request, db)


def _user_out(user: User) -> UserOut:
    return UserOut(id=str(user.id), provider=user.provider, nickname=user.nickname, avatar_url=user.avatar_url)


# ---------------------------------------------------------------- 프로필·장소·날씨
@router.get("/profiles", response_model=list[ProfileOut], summary="프로필 목록 (엔진 우선, 실패 시 정적)")
async def profiles(cfg: Settings = Depends(get_settings)) -> list[ProfileOut]:
    try:
        return [ProfileOut(**p) for p in await engine_client.profiles(cfg)]
    except Exception:  # noqa: BLE001
        return STATIC_PROFILES


@router.get("/place/search", response_model=PlaceSearchResponse, summary="장소 검색 (Kakao + 로컬 역·정류장)")
async def place_search(query: str = Query(..., min_length=1, max_length=100), lat: float | None = Query(None), lng: float | None = Query(None),
                       cfg: Settings = Depends(get_settings), db: AsyncSession = Depends(get_db)) -> PlaceSearchResponse:
    places, source = await search_places(cfg, query, lat, lng)
    db.add(PlaceSearch(query=query[:200], source=source, result_count=len(places)))
    await db.commit()
    return PlaceSearchResponse(places=places, source=source)


@router.get("/weather", response_model=WeatherOut, summary="날씨 컨텍스트 (현재 또는 출발 시각 예보)")
async def weather(lat: float = Query(..., ge=-90, le=90), lng: float = Query(..., ge=-180, le=180), at: datetime | None = Query(None),
                  cfg: Settings = Depends(get_settings)) -> WeatherOut:
    return await get_weather(cfg, lat, lng, at)


# ---------------------------------------------------------------- 경로
@router.post("/route", response_model=RouteSearchResponse, summary="교통약자 맞춤 경로 Top 3 (로그인 시 개인화 재정렬)")
async def route(req: RouteSearchRequest, cfg: Settings = Depends(get_settings), db: AsyncSession = Depends(get_db),
                user: User | None = Depends(get_user)) -> RouteSearchResponse:
    try:
        return await search_and_store(cfg, db, req, user)
    except engine_client.EngineError as exc:
        raise HTTPException(status_code=exc.status if exc.status in (422, 503) else 502, detail=exc.detail) from exc


@router.get("/route/{request_id}", response_model=StoredRouteResponse, summary="저장된 경로 결과 조회")
async def stored_route(request_id: str, db: AsyncSession = Depends(get_db)) -> StoredRouteResponse:
    rid = _uuid(request_id)
    stored = await get_stored(db, rid)
    if stored is None:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    return stored


@router.post("/route/{request_id}/choose", response_model=ChooseResponse, summary="경로 선택 기록 (로그인 사용자는 취향 학습)")
async def choose_route(request_id: str, body: ChooseRequest, cfg: Settings = Depends(get_settings), db: AsyncSession = Depends(get_db),
                       user: User | None = Depends(get_user)) -> ChooseResponse:
    rid = _uuid(request_id)
    try:
        res = await record_choice(cfg, db, rid, body.route_id, user)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if res is None:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    return res


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="request_id 형식이 올바르지 않습니다") from exc


# ---------------------------------------------------------------- 로그인
@router.get("/auth/providers", summary="설정된 로그인 공급자")
async def auth_providers(cfg: Settings = Depends(get_settings)) -> dict:
    return {"providers": auth.configured_providers(cfg), "dev_login": cfg.allow_dev_login}


@router.get("/auth/me", summary="현재 로그인 사용자 (게스트면 user: null)")
async def auth_me(user: User | None = Depends(get_user)) -> dict:
    return {"user": (_user_out(user).model_dump() if user else None)}


@router.post("/auth/logout", summary="로그아웃")
async def auth_logout(response: Response, cfg: Settings = Depends(get_settings)) -> dict:
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/{provider}/login", summary="OAuth 로그인 시작 (공급자로 리다이렉트)")
async def auth_login(provider: str, cfg: Settings = Depends(get_settings)) -> RedirectResponse:
    state = auth.new_state()
    url = auth.authorize_url(cfg, provider, state)
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(auth.STATE_COOKIE, state, httponly=True, samesite="lax", secure=cfg.cookie_secure, max_age=600, path="/")
    return response


@router.get("/auth/{provider}/callback", summary="OAuth 콜백 (세션 쿠키 발급 후 프론트로 리다이렉트)")
async def auth_callback(provider: str, request: Request, code: str | None = Query(None), state: str | None = Query(None),
                        error: str | None = Query(None), cfg: Settings = Depends(get_settings), db: AsyncSession = Depends(get_db)):
    if provider not in auth.PROVIDERS:
        raise HTTPException(status_code=404, detail="지원하지 않는 로그인 공급자입니다")
    if error or not code:
        return RedirectResponse(f"{cfg.frontend_url}?login=cancelled", status_code=302)
    expected = request.cookies.get(auth.STATE_COOKIE)
    if not expected or expected != state:
        raise HTTPException(status_code=400, detail="state 가 일치하지 않습니다")
    profile = await auth.exchange_code(cfg, provider, code, state)
    user = await auth.upsert_user(db, profile)
    response = RedirectResponse(f"{cfg.frontend_url}?login=ok", status_code=302)
    response.set_cookie(auth.SESSION_COOKIE, auth.issue_session(cfg, user), **auth.cookie_kwargs(cfg))
    response.delete_cookie(auth.STATE_COOKIE, path="/")
    return response


@router.post("/auth/dev/login", response_model=UserOut, summary="로컬 개발용 데모 로그인 (ALLOW_DEV_LOGIN=true 일 때만)")
async def auth_dev_login(response: Response, nickname: str = Query("데모 사용자", max_length=100), cfg: Settings = Depends(get_settings),
                         db: AsyncSession = Depends(get_db)) -> UserOut:
    if not cfg.allow_dev_login:
        raise HTTPException(status_code=404, detail="Not Found")
    user = await auth.upsert_user(db, auth.ProviderProfile("dev", nickname, nickname, ""))
    response.set_cookie(auth.SESSION_COOKIE, auth.issue_session(cfg, user), **auth.cookie_kwargs(cfg))
    return _user_out(user)


# ---------------------------------------------------------------- 개인화
@router.get("/me/preferences", response_model=PreferencesOut, summary="학습된 취향 요약")
async def my_preferences(db: AsyncSession = Depends(get_db), user: User | None = Depends(get_user)) -> PreferencesOut:
    if user is None:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    policy, _ = await load_policy(db, user.id)
    return PreferencesOut(updates=policy.updates, weights={k: round(v, 3) for k, v in policy.weights.items()}, summary=policy.summary())


@router.delete("/me/preferences", summary="학습된 취향 초기화")
async def reset_preferences(db: AsyncSession = Depends(get_db), user: User | None = Depends(get_user)) -> dict:
    if user is None:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    from .models import UserPolicy

    row = await db.get(UserPolicy, user.id)
    if row is not None:
        await db.delete(row)
        await db.commit()
    return {"ok": True}
