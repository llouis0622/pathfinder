import httpx

from app.config import settings
from app.schemas.place import PlaceResponseSchema, PlaceSchema


async def search_places(query: str, lat: float | None, lng: float | None) -> PlaceResponseSchema:
    """
    카카오 로컬 REST API를 호출하여 장소 검색 결과 반환.
    API 키 미설정 시 빈 결과 반환.
    """
    if not settings.kakao_rest_api_key:
        return PlaceResponseSchema(places=[])

    params: dict = {"query": query, "size": 10}
    if lat is not None:
        params["y"] = lat
    if lng is not None:
        params["x"] = lng

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(
            "https://dapi.kakao.com/v2/local/search/keyword.json",
            params=params,
            headers={"Authorization": f"KakaoAK {settings.kakao_rest_api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()

    places = [
        PlaceSchema(
            id=doc["id"],
            name=doc["place_name"],
            address=doc.get("road_address_name") or doc.get("address_name", ""),
            lat=float(doc["y"]),
            lng=float(doc["x"]),
            category=doc.get("category_name", ""),
        )
        for doc in data.get("documents", [])
    ]
    return PlaceResponseSchema(places=places)
