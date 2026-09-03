"""날씨 컨텍스트. 백엔드가 관측값을 채우고, 플래그는 여기서 일관되게 파생한다."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Sky = Literal["clear", "cloudy", "rain", "snow", "unknown"]

HEAT_FEELS_C = 28.0
HEATWAVE_FEELS_C = 33.0
COLD_FEELS_C = -5.0
COLDWAVE_FEELS_C = -12.0
RAIN_MM_PER_H = 0.5
BAD_AIR_PM10 = 81.0
WINDY_MS = 9.0


class WeatherContext(BaseModel):
    """관측값(선택) + 파생 플래그. 플래그를 직접 주면 관측값보다 우선한다."""

    source: str = "none"
    observed_at: str | None = None
    temp_c: float | None = None
    feels_like_c: float | None = None
    precipitation_mm: float | None = Field(default=None, description="시간당 강수량")
    wind_ms: float | None = None
    pm10: float | None = None
    sky: Sky = "unknown"

    heat: bool = False
    heatwave: bool = False
    cold: bool = False
    coldwave: bool = False
    rain: bool = False
    bad_air: bool = False
    windy: bool = False
    flags_explicit: bool = Field(default=False, description="True면 플래그를 관측값으로 다시 계산하지 않는다")

    @model_validator(mode="after")
    def _derive(self) -> "WeatherContext":
        if self.flags_explicit:
            if self.heatwave:
                self.heat = True
            if self.coldwave:
                self.cold = True
            return self
        feels = self.feels_like_c if self.feels_like_c is not None else self.temp_c
        if feels is not None:
            self.heat = feels >= HEAT_FEELS_C
            self.heatwave = feels >= HEATWAVE_FEELS_C
            self.cold = feels <= COLD_FEELS_C or (
                self.temp_c is not None and self.temp_c <= 0.0 and (self.wind_ms or 0.0) >= 5.0
            )
            self.coldwave = feels <= COLDWAVE_FEELS_C
        self.rain = (self.precipitation_mm or 0.0) >= RAIN_MM_PER_H or self.sky in ("rain", "snow")
        self.bad_air = (self.pm10 or 0.0) >= BAD_AIR_PM10
        self.windy = (self.wind_ms or 0.0) >= WINDY_MS
        return self

    @classmethod
    def none(cls) -> "WeatherContext":
        return cls()

    def active_flags(self) -> list[str]:
        return [f for f in ("heatwave", "heat", "coldwave", "cold", "rain", "bad_air", "windy") if getattr(self, f)]
