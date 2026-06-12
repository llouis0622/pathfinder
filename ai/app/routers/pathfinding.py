from fastapi import APIRouter
from pydantic import BaseModel

from app.models.pathfinding.base import Coordinate
from app.services.pathfinding_service import run_pathfinding

router = APIRouter(prefix="/api/pathfinding", tags=["pathfinding"])


class CoordinateSchema(BaseModel):
    lat: float
    lng: float


class PathfindingRequest(BaseModel):
    origin: CoordinateSchema
    destination: CoordinateSchema
    algorithm: str = "ksp"
    weights: dict = {}


class PathfindingResponse(BaseModel):
    algorithm: str
    path: list[CoordinateSchema]
    duration_min: float
    distance_m: float
    metadata: dict


@router.post(
    "",
    response_model=PathfindingResponse,
    summary="경로 탐색",
    description="지정된 알고리즘(ksp/ga/aco/tree)으로 출발지→도착지 경로를 탐색합니다.",
)
async def pathfinding(req: PathfindingRequest) -> PathfindingResponse:
    result = run_pathfinding(
        origin=Coordinate(lat=req.origin.lat, lng=req.origin.lng),
        destination=Coordinate(lat=req.destination.lat, lng=req.destination.lng),
        algorithm=req.algorithm,
        weights=req.weights,
    )
    return PathfindingResponse(
        algorithm=result.algorithm,
        path=[CoordinateSchema(lat=c.lat, lng=c.lng) for c in result.path],
        duration_min=result.duration_min,
        distance_m=result.distance_m,
        metadata=result.metadata,
    )
