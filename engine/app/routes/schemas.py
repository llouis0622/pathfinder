"""엔진 API 요청·응답 스키마."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ..cost.profiles import PROFILE_IDS
from ..cost.weather import WeatherContext

ProfileId = Literal["wheelchair", "elderly", "walking_aid", "visually_impaired"]
assert set(ProfileId.__args__) == set(PROFILE_IDS)  # type: ignore[attr-defined]


class LatLng(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class SearchOptions(BaseModel):
    k: int = Field(default=3, ge=1, le=5)
    time_budget_s: float | None = Field(default=None, ge=0.2, le=30.0)
    aco_iterations: int | None = Field(default=None, ge=1, le=500)
    aco_ants: int | None = Field(default=None, ge=1, le=200)
    ga_generations: int | None = Field(default=None, ge=0, le=200)
    seed: int | None = None
    use_ga: bool = True


class SearchRequest(BaseModel):
    origin: LatLng
    destination: LatLng
    profile: ProfileId
    departure_at: datetime | None = None
    weather: WeatherContext | None = None
    options: SearchOptions = Field(default_factory=SearchOptions)


class SlopeSegment(BaseModel):
    path: list[list[float]]
    grade_pct: float | None
    distance_m: float
    shade_ratio: float
    stairs: bool
    surface: str
    crossing: str


class LegOut(BaseModel):
    kind: Literal["walk", "ride", "vertical"]
    mode: str
    path: list[list[float]]
    distance_m: float
    duration_s: float
    wait_s: float = 0.0
    # ride
    route_id: str = ""
    route_name: str = ""
    from_name: str = ""
    to_name: str = ""
    stop_count: int = 0
    low_floor_ratio: float | None = None
    # vertical
    facility: str = ""
    station_name: str = ""
    verified: bool | None = None
    # walk
    uphill_m: float = 0.0
    downhill_m: float = 0.0
    max_grade_pct: float | None = None
    stairs_count: int = 0
    step_count: int = 0
    shade_ratio: float | None = None
    unshaded_m: float = 0.0
    crossings: int = 0
    segments: list[SlopeSegment] = Field(default_factory=list)


class RouteFeaturesOut(BaseModel):
    total_duration_s: float
    walk_distance_m: float
    walk_duration_s: float
    ride_duration_s: float
    wait_duration_s: float
    boardings: int
    transfers: int
    max_grade_pct: float | None
    avg_grade_pct: float | None
    uphill_m: float
    downhill_m: float
    stairs_count: int
    total_steps: int
    elevator_count: int
    unverified_vertical_count: int
    shade_ratio: float | None
    unshaded_walk_m: float
    crossings: int
    rough_surface_m: float
    modes: list[str]
    generalized_cost_s: float


class RouteOut(BaseModel):
    id: str
    rank: int
    summary: str
    badges: list[str]
    cautions: list[str]
    total_duration_min: float
    walk_distance_m: float
    transfers: int
    origin_algorithm: str
    features: RouteFeaturesOut
    legs: list[LegOut]
    path: list[list[float]]


class SearchMetadata(BaseModel):
    profile: str
    profile_label: str
    weather_flags: list[str]
    departure_at: str | None
    corridor_nodes: int
    corridor_edges: int
    blocked_edges: int
    snap_origin_m: float
    snap_destination_m: float
    shade_status: str
    shade_note: str
    solar_elevation_deg: float | None
    building_height_coverage: float | None
    elevation_resolution_m: int = 90
    aco: dict
    ga: dict
    archive_size: int
    elapsed_ms: float


class SearchResponse(BaseModel):
    routes: list[RouteOut]
    metadata: SearchMetadata
