"""엔진 API 라우터: 프로필 목록, 경로 탐색."""
from __future__ import annotations

import logging
from dataclasses import replace

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..cost.profiles import PROFILES
from ..routes.schemas import SearchRequest, SearchResponse
from ..search.aco import ACOParams
from ..search.ga import GAParams
from ..search.pipeline import NoRouteError, search_routes

log = logging.getLogger("engine.api")
router = APIRouter(prefix="/api", tags=["engine"])

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
    try:
        return search_routes(request.app.state.store, body, replace(aco), replace(ga))
    except NoRouteError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("탐색 실패")
        raise HTTPException(status_code=500, detail=f"탐색 중 오류: {type(exc).__name__}") from exc
