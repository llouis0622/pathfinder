"""날씨 조회. 공급자: Open-Meteo(기본, 키 불필요) / OpenWeather / none. 수동 플래그 모드 지원.

출발 시각이 미래(30분 이후)면 시간별 예보에서 해당 시각을 고른다. 실패하면 source="unavailable" 로
플래그 없는 컨텍스트를 돌려주고, 응답 note 에 사유를 남긴다.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from .. import http
from ..config import Settings
from ..schemas import ManualWeather, WeatherOut

log = logging.getLogger("backend.weather")
KST = ZoneInfo("Asia/Seoul")
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
OPENWEATHER_AIR_URL = "https://api.openweathermap.org/data/2.5/air_pollution"

HEAT_FEELS_C, HEATWAVE_FEELS_C = 28.0, 33.0
COLD_FEELS_C, COLDWAVE_FEELS_C = -5.0, -12.0
RAIN_MM, BAD_AIR_PM10, WINDY_MS = 0.5, 81.0, 9.0

_cache: dict[tuple, tuple[float, WeatherOut]] = {}


def derive_flags(w: WeatherOut) -> list[str]:
    flags: list[str] = []
    feels = w.feels_like_c if w.feels_like_c is not None else w.temp_c
    if feels is not None:
        if feels >= HEATWAVE_FEELS_C:
            flags.append("heatwave")
        if feels >= HEAT_FEELS_C:
            flags.append("heat")
        if feels <= COLDWAVE_FEELS_C:
            flags.append("coldwave")
        if feels <= COLD_FEELS_C or (w.temp_c is not None and w.temp_c <= 0 and (w.wind_ms or 0) >= 5):
            flags.append("cold")
    if (w.precipitation_mm or 0) >= RAIN_MM or w.sky in ("rain", "snow"):
        flags.append("rain")
    if (w.pm10 or 0) >= BAD_AIR_PM10:
        flags.append("bad_air")
    if (w.wind_ms or 0) >= WINDY_MS:
        flags.append("windy")
    return flags


def _sky_from_wmo(code: int | None) -> str:
    if code is None:
        return "unknown"
    if code in (0, 1):
        return "clear"
    if code in (2, 3, 45, 48):
        return "cloudy"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code >= 51:
        return "rain"
    return "unknown"


def _sky_from_openweather(main: str | None) -> str:
    m = (main or "").lower()
    if m in ("clear",):
        return "clear"
    if m in ("clouds", "mist", "haze", "fog"):
        return "cloudy"
    if m in ("snow",):
        return "snow"
    if m in ("rain", "drizzle", "thunderstorm"):
        return "rain"
    return "unknown"


def _target_hour(at: datetime | None) -> datetime | None:
    if at is None:
        return None
    at = at.astimezone(KST) if at.tzinfo else at.replace(tzinfo=KST)
    if at - datetime.now(KST) < timedelta(minutes=30):
        return None
    return at.replace(minute=0, second=0, microsecond=0)


async def _open_meteo(client: httpx.AsyncClient, lat: float, lng: float, at: datetime | None) -> WeatherOut:
    target = _target_hour(at)
    params = {
        "latitude": lat, "longitude": lng, "timezone": "Asia/Seoul", "wind_speed_unit": "ms", "forecast_days": 3,
        "current": "temperature_2m,apparent_temperature,precipitation,wind_speed_10m,weather_code",
        "hourly": "temperature_2m,apparent_temperature,precipitation,wind_speed_10m,weather_code",
    }
    r = await client.get(OPEN_METEO_URL, params=params)
    r.raise_for_status()
    data = r.json()
    out = WeatherOut(source="open_meteo")
    if target is not None:
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        key = target.strftime("%Y-%m-%dT%H:00")
        if key in times:
            i = times.index(key)
            out.temp_c = hourly["temperature_2m"][i]
            out.feels_like_c = hourly["apparent_temperature"][i]
            out.precipitation_mm = hourly["precipitation"][i]
            out.wind_ms = hourly["wind_speed_10m"][i]
            out.sky = _sky_from_wmo(hourly["weather_code"][i])
            out.forecast_for = target.isoformat()
    if out.forecast_for is None:
        cur = data.get("current", {})
        out.temp_c = cur.get("temperature_2m")
        out.feels_like_c = cur.get("apparent_temperature")
        out.precipitation_mm = cur.get("precipitation")
        out.wind_ms = cur.get("wind_speed_10m")
        out.sky = _sky_from_wmo(cur.get("weather_code"))
        out.observed_at = cur.get("time")
    try:
        air = await client.get(OPEN_METEO_AIR_URL, params={"latitude": lat, "longitude": lng, "current": "pm10", "hourly": "pm10",
                                                            "timezone": "Asia/Seoul", "forecast_days": 3})
        air.raise_for_status()
        adata = air.json()
        if target is not None and target.strftime("%Y-%m-%dT%H:00") in adata.get("hourly", {}).get("time", []):
            i = adata["hourly"]["time"].index(target.strftime("%Y-%m-%dT%H:00"))
            out.pm10 = adata["hourly"]["pm10"][i]
        else:
            out.pm10 = adata.get("current", {}).get("pm10")
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        out.note = f"미세먼지 조회 실패({type(exc).__name__})"
    return out


async def _openweather(client: httpx.AsyncClient, lat: float, lng: float, key: str) -> WeatherOut:
    r = await client.get(OPENWEATHER_URL, params={"lat": lat, "lon": lng, "appid": key, "units": "metric"})
    r.raise_for_status()
    d = r.json()
    main = d.get("main", {})
    out = WeatherOut(
        source="openweather", temp_c=main.get("temp"), feels_like_c=main.get("feels_like"),
        precipitation_mm=(d.get("rain", {}).get("1h", 0.0) or 0.0) + (d.get("snow", {}).get("1h", 0.0) or 0.0),
        wind_ms=d.get("wind", {}).get("speed"), sky=_sky_from_openweather((d.get("weather") or [{}])[0].get("main")),
        observed_at=(datetime.fromtimestamp(d["dt"], tz=timezone.utc).astimezone(KST).isoformat() if d.get("dt") else None),
    )
    try:
        air = await client.get(OPENWEATHER_AIR_URL, params={"lat": lat, "lon": lng, "appid": key})
        air.raise_for_status()
        out.pm10 = (air.json().get("list") or [{}])[0].get("components", {}).get("pm10")
    except (httpx.HTTPError, ValueError) as exc:
        out.note = f"미세먼지 조회 실패({type(exc).__name__})"
    return out


def manual_weather(flags: ManualWeather | None) -> WeatherOut:
    active = [f for f in ("heat", "heatwave", "cold", "coldwave", "rain", "bad_air", "windy") if flags and getattr(flags, f)]
    if "heatwave" in active and "heat" not in active:
        active.append("heat")
    if "coldwave" in active and "cold" not in active:
        active.append("cold")
    return WeatherOut(source="manual", flags=active, note="사용자가 직접 지정한 날씨 조건")


async def get_weather(cfg: Settings, lat: float, lng: float, at: datetime | None = None, mode: str = "auto",
                      manual: ManualWeather | None = None) -> WeatherOut:
    if mode == "none" or cfg.weather_provider == "none":
        return WeatherOut(source="none", note="날씨를 반영하지 않습니다")
    if mode == "manual":
        return manual_weather(manual)
    target = _target_hour(at)
    cache_key = (cfg.weather_provider, round(lat, 2), round(lng, 2), target.isoformat() if target else None)
    now = time.monotonic()
    hit = _cache.get(cache_key)
    if hit and now - hit[0] < cfg.weather_cache_ttl_s:
        return hit[1]
    try:
        async with http.client(timeout=8.0) as client:
            if cfg.weather_provider == "openweather":
                if not cfg.openweather_api_key:
                    return WeatherOut(source="unavailable", note="OPENWEATHER_API_KEY 가 설정되지 않았습니다")
                out = await _openweather(client, lat, lng, cfg.openweather_api_key)
            else:
                out = await _open_meteo(client, lat, lng, at)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        log.warning("날씨 조회 실패: %s", exc)
        return WeatherOut(source="unavailable", note=f"날씨 조회 실패({type(exc).__name__}); 날씨 없이 탐색")
    out.flags = derive_flags(out)
    _cache[cache_key] = (now, out)
    return out


def clear_cache() -> None:
    _cache.clear()
