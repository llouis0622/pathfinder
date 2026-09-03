"""DEM 기반 노드 고도·엣지 경사 (KT-10 ai/features/elevation.py 의 지역 DEM 부분 이식).

부산 90 m DEM(EPSG:5179)을 메모리에 올리고, 유효한 이웃 셀만으로 가중치를 재정규화하는
이중선형 보간으로 고도를 구한다. 결과는 90 m 격자 지형 수준의 추정치다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..graph.geo import haversine_m
from ..graph.model import Graph

SAMPLE_SPACING_M = 45.0
MAX_ABS_GRADE_PCT = 35.0
SHORT_EDGE_M = 30.0
DEFAULT_DEM = Path(__file__).resolve().parents[3] / "data" / "dem" / "busan_dem_clipped_90m.tif"


@dataclass
class Dem:
    values: np.ndarray
    transform: object          # affine.Affine
    crs: object
    nodata: float | None
    resolution_m: float

    @classmethod
    def load(cls, path: str | Path = DEFAULT_DEM) -> "Dem":
        import rasterio

        with rasterio.open(path) as ds:
            if ds.count != 1 or ds.crs is None:
                raise ValueError("DEM은 단일 밴드와 CRS가 있어야 합니다.")
            values = ds.read(1).astype(np.float64)
            return cls(values, ds.transform, ds.crs, (float(ds.nodata) if ds.nodata is not None else None), float(ds.res[0]))

    def _measured(self, v: float) -> bool:
        return math.isfinite(v) and (self.nodata is None or abs(v - self.nodata) >= 1e-6)

    def sample(self, lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
        """위경도 배열 → 고도(m). 유효 셀이 없으면 NaN."""
        from rasterio.warp import transform as transform_coordinates

        lats = np.asarray(lats, dtype=np.float64)
        lngs = np.asarray(lngs, dtype=np.float64)
        if lats.size == 0:
            return np.zeros(0)
        xs, ys = transform_coordinates("EPSG:4326", self.crs, lngs.tolist(), lats.tolist())
        inverse = ~self.transform
        h, w = self.values.shape
        out = np.full(lats.size, np.nan)
        for i, (x, y) in enumerate(zip(xs, ys)):
            px, py = inverse @ (x, y) if hasattr(inverse, '__matmul__') else inverse * (x, y)
            px -= 0.5
            py -= 0.5
            x0, y0 = math.floor(px), math.floor(py)
            if x0 < 0 or y0 < 0 or x0 + 1 >= w or y0 + 1 >= h:
                continue
            dx, dy = px - x0, py - y0
            corners = (
                (self.values[y0, x0], (1 - dx) * (1 - dy)), (self.values[y0, x0 + 1], dx * (1 - dy)),
                (self.values[y0 + 1, x0], (1 - dx) * dy), (self.values[y0 + 1, x0 + 1], dx * dy),
            )
            tw = acc = 0.0
            for v, wt in corners:
                if self._measured(float(v)):
                    tw += wt
                    acc += float(v) * wt
            if tw > 0:
                out[i] = acc / tw
        return out


def _resample(points: list[tuple[float, float]], spacing: float) -> list[tuple[float, float]]:
    """폴리라인을 누적 거리 기준으로 spacing 이하 간격으로 다시 샘플링한다 (양 끝 포함)."""
    if len(points) < 2:
        return list(points)
    out = [points[0]]
    for (lat1, lng1), (lat2, lng2) in zip(points, points[1:]):
        seg = float(haversine_m(lat1, lng1, lat2, lng2))
        n = max(1, int(math.ceil(seg / spacing)))
        for k in range(1, n + 1):
            t = k / n
            out.append((lat1 + (lat2 - lat1) * t, lng1 + (lng2 - lng1) * t))
    return out


@dataclass
class ElevationReport:
    nodes_measured: int
    nodes_total: int
    edges_graded: int
    edges_total: int
    clipped: int


def enrich_elevation(graph: Graph, dem: Dem) -> tuple[Graph, ElevationReport]:
    """노드 elevation_m, 보행/link 엣지 grade_pct(순 경사)·max_grade_pct(구간 최대 |경사|)를 채운다."""
    lat, lng = graph.nodes["lat"], graph.nodes["lng"]
    node_z = dem.sample(lat, lng)
    graph.nodes["elevation_m"] = node_z.astype(np.float32)
    e = graph.edges
    walk = np.isin(e["kind"], ["walk", "link", "transfer"])
    grade = np.full(graph.num_edges, np.nan)
    max_grade = np.full(graph.num_edges, np.nan)
    clipped = 0
    # 모든 보행 엣지의 표본점을 모아 한 번에 샘플링
    sample_pts: list[tuple[float, float]] = []
    spans: list[tuple[int, int, int]] = []
    for i in np.nonzero(walk)[0]:
        pts = _resample(graph.edge_geometry(int(i)), SAMPLE_SPACING_M)
        spans.append((int(i), len(sample_pts), len(pts)))
        sample_pts.extend(pts)
    if sample_pts:
        arr = np.asarray(sample_pts)
        zs = dem.sample(arr[:, 0], arr[:, 1])
        for i, start, count in spans:
            pts = arr[start:start + count]
            z = zs[start:start + count]
            L = float(e["length_m"][i])
            if L <= 0:
                continue
            if np.isnan(z[0]) or np.isnan(z[-1]):
                # 끝점 결측이면 노드 고도로 대체 시도
                z0 = node_z[graph.src[i]] if np.isnan(z[0]) else z[0]
                z1 = node_z[graph.dst[i]] if np.isnan(z[-1]) else z[-1]
                if np.isnan(z0) or np.isnan(z1):
                    continue
                net = (z1 - z0) / L * 100.0
                segs = np.array([net])
            else:
                net = (z[-1] - z[0]) / L * 100.0
                d = haversine_m(pts[:-1, 0], pts[:-1, 1], pts[1:, 0], pts[1:, 1])
                valid = ~np.isnan(z[:-1]) & ~np.isnan(z[1:]) & (d >= 1.0)
                segs = (z[1:][valid] - z[:-1][valid]) / d[valid] * 100.0 if valid.any() else np.array([net])
            if abs(net) > MAX_ABS_GRADE_PCT:
                net = math.copysign(MAX_ABS_GRADE_PCT, net)
                clipped += 1
            m = float(np.max(np.abs(segs))) if segs.size else abs(net)
            grade[i] = net
            max_grade[i] = min(max(m, abs(net)), MAX_ABS_GRADE_PCT)
    graph.edges["grade_pct"] = grade.astype(np.float32)
    graph.edges["max_grade_pct"] = max_grade.astype(np.float32)
    report = ElevationReport(int(np.count_nonzero(~np.isnan(node_z))), graph.num_nodes,
                             int(np.count_nonzero(~np.isnan(grade))), int(walk.sum()), clipped)
    return graph, report
