"""백엔드 API 스키마. 경로 본문(routes[])은 엔진 SearchResponse.routes 를 그대로 전달한다."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ProfileId = Literal["wheelchair", "elderly", "walking_aid", "visually_impaired"]
WeatherMode = Literal["auto", "manual", "none"]


class NamedPoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    name: str = ""


class ManualWeather(BaseModel):
    heat: bool = False
    heatwave: bool = False
    cold: bool = False
    coldwave: bool = False
    rain: bool = False
    bad_air: bool = False
    windy: bool = False


class RouteSearchOptions(BaseModel):
    k: int = Field(default=3, ge=1, le=5)
    time_budget_s: float | None = Field(default=None, ge=0.2, le=30.0)
    seed: int | None = None


class RouteSearchRequest(BaseModel):
    origin: NamedPoint
    destination: NamedPoint
    profile: ProfileId
    departure_at: datetime | None = None
    weather_mode: WeatherMode = "auto"
    manual_weather: ManualWeather | None = None
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
        payload: dict[str, Any] = {
            "source": self.source, "observed_at": self.observed_at, "temp_c": self.temp_c, "feels_like_c": self.feels_like_c,
            "precipitation_mm": self.precipitation_mm, "wind_ms": self.wind_ms, "pm10": self.pm10, "sky": self.sky,
        }
        if self.source == "manual":
            payload["flags_explicit"] = True
            for f in ("heat", "heatwave", "cold", "coldwave", "rain", "bad_air", "windy"):
                payload[f] = f in self.flags
        return payload


class RouteSearchResponse(BaseModel):
    request_id: str
    profile: str
    departure_at: str | None
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
