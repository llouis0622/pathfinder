"""NOAA 근사식 태양 위치 (KT-10 backend/app/shade.py 이식)."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def to_kst(moment: datetime) -> datetime:
    return moment.replace(tzinfo=KST) if moment.tzinfo is None else moment.astimezone(KST)


def solar_position(moment: datetime, lat: float, lng: float) -> tuple[float, float]:
    """(방위각[북=0, 시계방향, 도], 고도각[도])."""
    local = to_kst(moment)
    utc = local.astimezone(timezone.utc)
    day = utc.timetuple().tm_yday
    fractional_hour = utc.hour + utc.minute / 60 + utc.second / 3600
    gamma = 2 * math.pi / 365 * (day - 1 + (fractional_hour - 12) / 24)
    equation_of_time = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    declination = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )
    true_solar_minutes = (
        local.hour * 60 + local.minute + local.second / 60 + equation_of_time + 4 * lng - 60 * 9
    ) % 1440
    hour_angle = math.radians(true_solar_minutes / 4 - 180)
    latitude = math.radians(lat)
    cos_zenith = math.sin(latitude) * math.sin(declination) + math.cos(latitude) * math.cos(declination) * math.cos(hour_angle)
    zenith = math.acos(max(-1.0, min(1.0, cos_zenith)))
    elevation = 90 - math.degrees(zenith)
    azimuth = math.degrees(math.atan2(
        math.sin(hour_angle),
        math.cos(hour_angle) * math.sin(latitude) - math.tan(declination) * math.cos(latitude),
    ))
    return (azimuth + 180) % 360, elevation


def round_to_bucket(moment: datetime, minutes: int = 30) -> datetime:
    local = to_kst(moment)
    total = local.hour * 60 + local.minute
    bucket = int(round(total / minutes) * minutes) % 1440
    return local.replace(hour=bucket // 60, minute=bucket % 60, second=0, microsecond=0)
