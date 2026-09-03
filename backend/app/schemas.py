"""백엔드 API 스키마. 경로 본문(routes[])은 엔진 SearchResponse.routes 를 그대로 전달한다."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ProfileId = Literal["wheelchair", "elderly", "walking_aid", "visually_impaired"]


class NamedPoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    name: str = ""


class RouteSearchOptions(BaseModel):
    k: int = Field(default=3, ge=1, le=5)
    time_budget_s: float | None = Field(default=None, ge=0.2, le=30.0)
    seed: int | None = None


class RouteSearchRequest(BaseModel):
    """날씨는 항상 실시간(또는 출발 시각 예보)으로 반영한다. 경사 회피는 엔진 기본값이며, 그늘 우선만 선택한다."""

    origin: NamedPoint
    destination: NamedPoint
    profile: ProfileId
    departure_at: datetime | None = Field(default=None, description="없으면 지금 출발")
    prefer_shade: bool = False
    options: RouteSearchOptions = Field(default_factory=RouteSearchOptions)


class WeatherOut(BaseModel):
    source: str = "none"
    observed_at: str | None = None
    forecast_for: str | None = None
    temp_c: float | None = None
    feels_like_c: float | None = None
    precipitation_mm: float | None = None
    wind_ms: float | None = None
    pm10: float | None = None
    sky: str = "unknown"
    flags: list[str] = Field(default_factory=list)
    note: str = ""

    def to_engine(self) -> dict[str, Any]:
        """엔진 WeatherContext 입력."""
        return {
            "source": self.source, "observed_at": self.observed_at, "temp_c": self.temp_c, "feels_like_c": self.feels_like_c,
            "precipitation_mm": self.precipitation_mm, "wind_ms": self.wind_ms, "pm10": self.pm10, "sky": self.sky,
        }


class RouteSearchResponse(BaseModel):
    request_id: str
    profile: str
    departure_at: str | None
    prefer_shade: bool
    weather: WeatherOut
    routes: list[dict[str, Any]]
    metadata: dict[str, Any]


class StoredRouteResponse(BaseModel):
    request_id: str
    created_at: str
    profile: str
    status: str
    origin: NamedPoint
    destination: NamedPoint
    weather: dict[str, Any] | None
    routes: list[dict[str, Any]]
    metadata: dict[str, Any] | None


class PlaceOut(BaseModel):
    id: str
    name: str
    address: str = ""
    lat: float
    lng: float
    category: str = ""
    source: str = ""


class PlaceSearchResponse(BaseModel):
    places: list[PlaceOut]
    source: str


class ProfileOut(BaseModel):
    id: str
    label: str
    description: str = ""
    speed_mps: float | None = None
