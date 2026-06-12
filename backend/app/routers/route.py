from fastapi import APIRouter

from app.schemas.route import RouteRequestSchema, RouteResponseSchema
from app.services.route_service import get_route

router = APIRouter(prefix="/api/route", tags=["route"])


@router.post(
    "",
    response_model=RouteResponseSchema,
    summary="경로 추천",
    description="출발지·도착지·프로필 정보를 받아 AI 서버에서 최적 경로를 반환합니다.",
)
async def recommend_route(req: RouteRequestSchema) -> RouteResponseSchema:
    return await get_route(req)
