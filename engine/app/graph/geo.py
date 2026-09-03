"""좌표 유틸리티. 모든 함수는 numpy 배열과 스칼라를 함께 받는다."""
from __future__ import annotations

import math

import numpy as np

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1, lng1, lat2, lng2):
    """두 지점(도 단위) 사이 대원 거리(m). 배열 브로드캐스팅을 지원한다."""
    lat1 = np.radians(lat1)
    lat2 = np.radians(lat2)
    dlat = lat2 - lat1
    dlng = np.radians(np.asarray(lng2) - np.asarray(lng1))
    h = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlng / 2) ** 2
    return EARTH_RADIUS_M * 2 * np.arcsin(np.sqrt(np.clip(h, 0.0, 1.0)))


def project_local(lat, lng, ref_lat: float, ref_lng: float):
    """기준점 중심의 등장방형 로컬 평면(m). 회랑 수 km 규모에서 충분히 정확하다."""
    x = (np.asarray(lng, dtype=np.float64) - ref_lng) * 111_320.0 * math.cos(math.radians(ref_lat))
    y = (np.asarray(lat, dtype=np.float64) - ref_lat) * 110_540.0
    return x, y


def unproject_local(x, y, ref_lat: float, ref_lng: float):
    lng = np.asarray(x, dtype=np.float64) / (111_320.0 * math.cos(math.radians(ref_lat))) + ref_lng
    lat = np.asarray(y, dtype=np.float64) / 110_540.0 + ref_lat
    return lat, lng


def polyline_length_m(coords) -> float:
    """[(lat, lng), ...] 폴리라인 길이(m)."""
    if len(coords) < 2:
        return 0.0
    arr = np.asarray(coords, dtype=np.float64)
    return float(np.sum(haversine_m(arr[:-1, 0], arr[:-1, 1], arr[1:, 0], arr[1:, 1])))
