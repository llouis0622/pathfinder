from fastapi import APIRouter, Query

from app.schemas.place import PlaceResponseSchema
from app.services.place_service import search_places

router = APIRouter(prefix="/api/place", tags=["place"])


@router.get(
    "/search",
    response_model=PlaceResponseSchema,
    summary="장소 검색",
    description="카카오 로컬 API를 통해 장소를 검색하고 결과를 반환합니다.",
)
async def search(
    query: str = Query(..., description="검색어"),
    lat: float | None = Query(None, description="기준 위도"),
    lng: float | None = Query(None, description="기준 경도"),
) -> PlaceResponseSchema:
    return await search_places(query, lat, lng)
