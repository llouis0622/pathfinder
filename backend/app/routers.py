"""백엔드 API 라우터."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings
from .models import PlaceSearch
from .schemas import PlaceSearchResponse, ProfileOut, RouteSearchRequest, RouteSearchResponse, StoredRouteResponse, WeatherOut
from .services import engine_client
from .services.places import search_places
from .services.route import get_stored, search_and_store
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


@router.post("/route", response_model=RouteSearchResponse, summary="교통약자 맞춤 경로 Top 3")
async def route(req: RouteSearchRequest, cfg: Settings = Depends(get_settings), db: AsyncSession = Depends(get_db)) -> RouteSearchResponse:
    try:
        return await search_and_store(cfg, db, req)
    except engine_client.EngineError as exc:
        raise HTTPException(status_code=exc.status if exc.status in (422, 503) else 502, detail=exc.detail) from exc


@router.get("/route/{request_id}", response_model=StoredRouteResponse, summary="저장된 경로 결과 조회")
async def stored_route(request_id: str, db: AsyncSession = Depends(get_db)) -> StoredRouteResponse:
    try:
        rid = uuid.UUID(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="request_id 형식이 올바르지 않습니다") from exc
    stored = await get_stored(db, rid)
    if stored is None:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다")
    return stored
