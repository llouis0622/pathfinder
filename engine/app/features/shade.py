"""건물 그림자 기반 보행 엣지 그늘 비율.

건물 footprint를 태양 반대 방향으로 `height / tan(elevation)` 만큼 스윕한 다각형을
그림자로 보고, 실외 보행 엣지의 (그림자 ∩ 엣지 길이) / (엣지 길이)를 구한다.
가로수·지형 그림자는 포함하지 않는다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..graph.geo import project_local
from ..graph.model import TRI_TRUE, Graph
from ..graph.store import Building
from .solar import round_to_bucket, solar_position

BUILDING_MARGIN_DEG = 0.003    # 건물 그림자가 회랑 밖에서 들어오므로 bbox 를 ~300m 넓혀 건물을 읽는다

MIN_ELEVATION_DEG = 3.0
MAX_BUILDING_HEIGHT_M = 1000.0
LEVEL_HEIGHT_M = 3.3


@dataclass
class ShadeInfo:
    status: str                       # computed | not_daylight | no_buildings | disabled
    evaluated_at: str | None = None
    solar_azimuth_deg: float | None = None
    solar_elevation_deg: float | None = None
    building_count: int = 0
    known_height_count: int = 0
    note: str = ""

    @property
    def coverage(self) -> float | None:
        if self.building_count == 0:
            return None
        return self.known_height_count / self.building_count


def swept_shadow(polygon: Polygon, shift: tuple[float, float]) -> BaseGeometry:
    shifted = affinity.translate(polygon, xoff=shift[0], yoff=shift[1])
    pieces: list[BaseGeometry] = [polygon, shifted]
    for ring in [polygon.exterior, *polygon.interiors]:
        coords = list(ring.coords)
        for left, right in zip(coords, coords[1:]):
            pieces.append(Polygon([left, right, (right[0] + shift[0], right[1] + shift[1]), (left[0] + shift[0], left[1] + shift[1])]))
    return unary_union(pieces)


def _valid_height(h: float | None) -> float | None:
    if h is None or not math.isfinite(h) or h <= 0 or h > MAX_BUILDING_HEIGHT_M:
        return None
    return float(h)


def edge_shade_ratios(graph: Graph, buildings: list[Building], moment: datetime | None) -> tuple[np.ndarray, ShadeInfo]:
    """실외 보행 엣지의 그늘 비율 배열과 계산 상태."""
    E = graph.num_edges
    ratios = np.zeros(E, dtype=np.float64)
    if moment is None:
        return ratios, ShadeInfo("disabled", note="출발 시각이 없어 그늘을 계산하지 않았습니다.")
    if E == 0:
        return ratios, ShadeInfo("no_buildings")
    bucket = round_to_bucket(moment)
    ref_lat = float(np.mean(graph.nodes["lat"]))
    ref_lng = float(np.mean(graph.nodes["lng"]))
    az, el = solar_position(bucket, ref_lat, ref_lng)
    info = ShadeInfo("computed", bucket.isoformat(), round(az, 2), round(el, 2), len(buildings), 0)
    if el <= MIN_ELEVATION_DEG:
        info.status = "not_daylight"
        info.note = "태양 고도가 낮아 건물 그늘을 계산하지 않았습니다."
        return ratios, info
    if not buildings:
        info.status = "no_buildings"
        info.note = "회랑 안에 건물 정보가 없습니다."
        return ratios, info

    tan_el = math.tan(math.radians(el))
    shadow_az = math.radians((az + 180) % 360)
    shadows: list[BaseGeometry] = []
    for b in buildings:
        h = _valid_height(b.height_m)
        if h is None:
            continue
        L = h / tan_el
        shift = (math.sin(shadow_az) * L, math.cos(shadow_az) * L)
        fx, fy = project_local([p[0] for p in b.footprint], [p[1] for p in b.footprint], ref_lat, ref_lng)
        holes = []
        for ring in b.holes:
            hx, hy = project_local([p[0] for p in ring], [p[1] for p in ring], ref_lat, ref_lng)
            holes.append(list(zip(hx, hy)))
        try:
            poly = Polygon(list(zip(fx, fy)), holes)
        except ValueError:
            continue   # 점이 모자란 외곽/구멍
        if poly.is_empty or not poly.is_valid or poly.area <= 0:
            poly = poly.buffer(0)
            if poly.is_empty or poly.area <= 0:
                continue
        info.known_height_count += 1
        shadows.append(swept_shadow(poly, shift))
    if not shadows:
        info.status = "no_buildings"
        info.note = "높이를 아는 건물이 없어 그늘을 계산하지 않았습니다."
        return ratios, info

    tree = STRtree(shadows)
    kinds = graph.edges["kind"]
    outdoor = graph.edges["indoor"] != TRI_TRUE
    for e in range(E):
        if kinds[e] not in ("walk", "link") or not outdoor[e]:
            continue
        pts = graph.edge_geometry(e)
        xs, ys = project_local([p[0] for p in pts], [p[1] for p in pts], ref_lat, ref_lng)
        line = LineString(list(zip(xs, ys)))
        if line.length <= 0:
            continue
        hits = tree.query(line)
        if len(hits) == 0:
            continue
        shadow = unary_union([shadows[i] for i in hits])
        ratios[e] = min(1.0, line.intersection(shadow).length / line.length)
    return ratios, info
