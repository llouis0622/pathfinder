import math
import httpx

from app.config import settings
from app.schemas.route import (
    Coordinate,
    RouteRequestSchema,
    RouteResponseSchema,
    RouteResultSchema,
)


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 좌표 간 직선거리(km) 계산"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


async def get_route(req: RouteRequestSchema) -> RouteResponseSchema:
    """
    AI 서버에 경로 탐색 요청 후 결과 반환.
    AI 서버 호출 실패 시 출발지→도착지 직선 좌표로 플레이스홀더 응답 반환.
    """
    weights_dict = req.weights.model_dump()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.ai_server_url}/api/pathfinding",
                json={
                    "origin": {"lat": req.origin.lat, "lng": req.origin.lng},
                    "destination": {"lat": req.destination.lat, "lng": req.destination.lng},
                    "algorithm": "ksp",
                    "weights": weights_dict,
                },
            )
            resp.raise_for_status()
            ai_data = resp.json()
            path = [Coordinate(**p) for p in ai_data["path"]]
            duration_min = ai_data["duration_min"]
            distance_m = ai_data["distance_m"]
            algorithm = ai_data["algorithm"]
    except Exception:
        # AI 서버 미연결 시 직선 좌표 플레이스홀더
        distance_km = _haversine_km(req.origin.lat, req.origin.lng, req.destination.lat, req.destination.lng)
        distance_m = distance_km * 1000
        duration_min = round(distance_km / 4.0 * 60, 1)  # 도보 평균 4km/h 기준
        path = [
            Coordinate(lat=req.origin.lat, lng=req.origin.lng),
            Coordinate(lat=req.destination.lat, lng=req.destination.lng),
        ]
        algorithm = "placeholder"

    route = RouteResultSchema(
        id="route_1",
        label="추천 경로",
        duration_min=duration_min,
        distance_m=distance_m,
        path=path,
        profile=req.profile,
        weights_applied=req.weights,
        algorithm=algorithm,
    )
    return RouteResponseSchema(routes=[route])
