from pydantic import BaseModel


class RouteWeights(BaseModel):
    avoid_stairs: bool = False       # 계단 회피
    elevator_priority: bool = False  # 엘리베이터 우선
    low_grade: bool = False          # 낮은 경사 우선
    min_transfer: bool = False       # 환승 최소화
    avoid_crowded: bool = False      # 혼잡 회피
    wide_sidewalk: bool = False      # 넓은 보도 우선
    shelter_nearby: bool = False     # 쉼터 근접
    low_walk_distance: bool = False  # 도보거리 최소화
    avoid_heat: bool = False         # 폭염 회피
    avoid_cold: bool = False         # 한파 회피


class Coordinate(BaseModel):
    lat: float
    lng: float


class NamedCoordinate(Coordinate):
    name: str


class RouteRequestSchema(BaseModel):
    origin: NamedCoordinate
    destination: NamedCoordinate
    profile: str
    weights: RouteWeights


class RouteResultSchema(BaseModel):
    id: str
    label: str
    duration_min: float
    distance_m: float
    path: list[Coordinate]
    profile: str
    weights_applied: RouteWeights
    algorithm: str


class RouteResponseSchema(BaseModel):
    routes: list[RouteResultSchema]
