"""엔진 API 라우터: 프로필 목록, 경로 탐색."""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request, Response
from prometheus_client import Counter, Histogram
from pydantic import BaseModel

from .. import tiles
from ..cost.profiles import PROFILES
from ..routes.schemas import SearchRequest, SearchResponse
from ..search.aco import ACOParams
from ..search.ga import GAParams
from ..search.pipeline import NoRouteError, search_routes
from ..stats import store_stats

log = logging.getLogger("engine.api")
router = APIRouter(prefix="/api", tags=["engine"])

SEARCHES = Counter("pathfinder_engine_searches_total", "엔진 탐색 수", ["profile", "status"])
SEARCH_SECONDS = Histogram("pathfinder_engine_search_seconds", "엔진 탐색 시간(초)", ["profile"], buckets=(0.1, 0.25, 0.5, 1, 2, 3, 5, 10, 30))
TILES = Counter("pathfinder_engine_tiles_total", "타일 요청", ["result"])

PROFILE_DESCRIPTIONS = {
    "wheelchair": "계단·급경사·좁은 보도·턱을 피하고 엘리베이터와 저상버스만 이용합니다.",
    "elderly": "계단과 급경사 부담을 줄이고 총 도보 거리를 짧게, 폭염·한파에 민감하게 봅니다.",
    "walking_aid": "보행보조기·목발 이용자. 계단 부담을 더 크게, 엘리베이터를 우선합니다.",
    "visually_impaired": "신호 없는 횡단을 피하고 점자블록·난간이 있는 길을 우선합니다.",
}


class ProfileOut(BaseModel):
    id: str
    label: str
    description: str
    speed_mps: float


@router.get("/profiles", response_model=list[ProfileOut], summary="지원 프로필")
def profiles() -> list[ProfileOut]:
    return [ProfileOut(id=p.id, label=p.label, description=PROFILE_DESCRIPTIONS.get(p.id, ""), speed_mps=p.speed_mps) for p in PROFILES.values()]


@router.post("/search", response_model=SearchResponse, summary="경로 탐색 (ACO + GA, Top K)")
def search(request: Request, body: SearchRequest) -> SearchResponse:
    cfg = request.app.state.settings
    aco = ACOParams(ants=cfg.aco_ants, iterations=cfg.aco_iterations, time_budget_s=cfg.engine_time_budget_s * 0.7)
    ga = GAParams(generations=cfg.ga_generations, time_budget_s=cfg.engine_time_budget_s * 0.3)
    if body.options.time_budget_s is None:
        body.options.time_budget_s = cfg.engine_time_budget_s
    import time as _time

    started = _time.perf_counter()
    try:
        result = search_routes(request.app.state.store, body, replace(aco), replace(ga))
    except NoRouteError as exc:
        SEARCHES.labels(body.profile, "no_route").inc()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        SEARCHES.labels(body.profile, "error").inc()
        log.exception("탐색 실패")
        raise HTTPException(status_code=500, detail=f"탐색 중 오류: {type(exc).__name__}") from exc
    SEARCHES.labels(body.profile, "ok").inc()
    SEARCH_SECONDS.labels(body.profile).observe(_time.perf_counter() - started)
    return result


# ---------------------------------------------------------------- 지도 타일·그늘
@router.get("/tiles/meta", summary="벡터 타일 메타 (최소 줌, 레이어)")
def tiles_meta() -> dict:
    return tiles.tile_meta()


@router.get("/tiles/{z}/{x}/{y}.mvt", summary="그래프 벡터 타일 (edges · facilities · stops)")
def tile(request: Request, z: int, x: int, y: int) -> Response:
    if not tiles.valid_tile(z, x, y):
        raise HTTPException(status_code=404, detail="타일 좌표가 올바르지 않습니다")
    cache = request.app.state.tile_cache
    before = cache.hits
    data = tiles.render_tile_cached(request.app.state.store, cache, z, x, y)
    TILES.labels("hit" if cache.hits > before else ("empty" if not data else "miss")).inc()
    headers = {"Cache-Control": "public, max-age=3600", "X-Tile-Cache": "hit" if cache.hits > before else "miss"}
    if not data:
        return Response(status_code=204, headers=headers)
    return Response(content=data, media_type=tiles.MVT_MEDIA_TYPE, headers=headers)


@router.get("/tiles/cache", summary="타일 캐시 상태")
def tile_cache_stats(request: Request) -> dict:
    return request.app.state.tile_cache.stats()


@router.get("/nearest-edge", summary="좌표에서 가장 가까운 보행·수직 엣지 (시설 제보 위치 매핑)")
def nearest_edge(request: Request, lat: float = Query(..., ge=-90, le=90), lng: float = Query(..., ge=-180, le=180),
                 max_distance_m: float = Query(60.0, ge=1, le=500)) -> dict:
    found = tiles.nearest_edge(request.app.state.store, lat, lng, max_distance_m)
    if found is None:
        raise HTTPException(status_code=422, detail=f"반경 {max_distance_m:.0f}m 안에 보행 엣지가 없습니다")
    return found


@router.get("/stats", summary="그래프 데이터 품질 통계")
def graph_quality(request: Request) -> dict:
    return store_stats(request.app.state.store)


@router.get("/shade", summary="화면 범위의 보행 엣지 그늘 비율 (시각 기준)")
def shade(request: Request, min_lat: float = Query(..., ge=-90, le=90), min_lng: float = Query(..., ge=-180, le=180),
          max_lat: float = Query(..., ge=-90, le=90), max_lng: float = Query(..., ge=-180, le=180), at: datetime | None = Query(None)) -> dict:
    moment = at or datetime.now(ZoneInfo("Asia/Seoul"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo("Asia/Seoul"))
    try:
        return tiles.shade_for_bbox(request.app.state.store, (min_lat, min_lng, max_lat, max_lng), moment)
    except tiles.ShadeBboxError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
