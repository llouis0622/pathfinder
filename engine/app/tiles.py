"""그래프 벡터 타일(MVT)과 화면 범위 실시간 그늘.

지도(MapLibre)가 확대됐을 때 보행 엣지의 경사·계단·턱·폭과 시설(계단·엘리베이터·횡단보도·정류장)을
타일로 내려보낸다. 메모리 스토어는 Python 으로 인코딩하고, PostGIS 스토어는 ST_AsMVT 로 만든다.
그늘은 태양 위치에 따라 바뀌므로 타일에 굽지 않고, 보이는 범위(bbox)와 시각으로 그때그때 계산한다.

레이어
- edges       : LineString. id, kind, mode, grade, max_grade, stairs, ramp, elevator, escalator, width, surface, crossing, kerb,
                tactile, handrail, indoor, route_name, name, steps
- facilities  : Point. id(=엣지 id), type(stairs|elevator|escalator|vertical|kerb|crossing), verified, name, steps, handrail, ramp, crossing, kerb
- stops       : Point. id(=노드 id), kind(stop|platform|entrance), name
"""
from __future__ import annotations

import math
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Any

import mapbox_vector_tile
import numpy as np
from shapely.geometry import LineString, Point

from .features.shade import BUILDING_MARGIN_DEG, edge_shade_ratios
from .graph.geo import haversine_m
from .graph.model import TRI_TRUE, Graph
from .graph.store import MemoryGraphStore

EXTENT = 4096
MIN_ZOOM = 14
MAX_ZOOM = 22
SHOWN_EDGE_KINDS = ("walk", "link", "vertical")
STOP_NODE_KINDS = ("stop", "platform", "entrance")
KERB_TYPES = ("raised", "rolled")
SHADE_MAX_SPAN_M = 3500.0            # 그늘 계산 bbox 한 변 상한
SHADE_BUILDING_MARGIN_DEG = BUILDING_MARGIN_DEG    # 건물 그림자가 밖에서 들어오므로 bbox 를 ~300m 넓혀 건물을 읽는다
R = 6378137.0

MVT_MEDIA_TYPE = "application/vnd.mapbox-vector-tile"


# ---------------------------------------------------------------- 좌표
def lnglat_to_merc(lng: float, lat: float) -> tuple[float, float]:
    lat = max(-85.05112878, min(85.05112878, lat))
    return R * math.radians(lng), R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def tile_bounds_merc(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    size = 2 * math.pi * R / (1 << z)
    minx = -math.pi * R + x * size
    maxy = math.pi * R - y * size
    return minx, maxy - size, minx + size, maxy


def tile_bbox(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """(min_lat, min_lng, max_lat, max_lng)."""
    minx, miny, maxx, maxy = tile_bounds_merc(z, x, y)

    def lat(y_m: float) -> float:
        return math.degrees(2 * math.atan(math.exp(y_m / R)) - math.pi / 2)

    return lat(miny), math.degrees(minx / R), lat(maxy), math.degrees(maxx / R)


def valid_tile(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_ZOOM and 0 <= x < (1 << z) and 0 <= y < (1 << z)


# ---------------------------------------------------------------- 속성
def _num(v: Any, digits: int = 1) -> float | None:
    if v is None:
        return None
    f = float(v)
    return None if math.isnan(f) else round(f, digits)


def edge_props(graph: Graph, e: int) -> dict[str, Any]:
    ed = graph.edges
    props: dict[str, Any] = {
        "kind": str(ed["kind"][e]), "mode": str(ed["mode"][e]), "stairs": int(ed["stairs"][e]), "ramp": int(ed["ramp"][e]),
        "elevator": int(ed["elevator"][e]), "escalator": int(ed["escalator"][e]), "tactile": int(ed["tactile"][e]),
        "handrail": int(ed["handrail"][e]), "indoor": int(ed["indoor"][e]), "surface": str(ed["surface"][e]),
        "crossing": str(ed["crossing"][e]), "kerb": str(ed["kerb"][e]), "route_name": str(ed["route_name"][e]), "name": str(ed["stop_name"][e]),
    }
    for key, col, digits in (("grade", "grade_pct", 1), ("max_grade", "max_grade_pct", 1), ("width", "width_m", 2), ("steps", "step_count", 0),
                             ("length", "length_m", 1)):
        v = _num(ed[col][e], digits)
        if v is not None:
            props[key] = v
    return {k: v for k, v in props.items() if v not in ("", None)}


def facility_type(graph: Graph, e: int) -> str | None:
    ed = graph.edges
    if str(ed["kind"][e]) == "vertical":
        if int(ed["elevator"][e]) == TRI_TRUE:
            return "elevator"
        if int(ed["escalator"][e]) == TRI_TRUE:
            return "escalator"
        return "stairs" if int(ed["stairs"][e]) == TRI_TRUE else "vertical"
    if int(ed["stairs"][e]) == TRI_TRUE:
        return "stairs"
    if str(ed["kerb"][e]) in KERB_TYPES:
        return "kerb"
    if str(ed["crossing"][e]):
        return "crossing"
    return None


def facility_props(graph: Graph, e: int, ftype: str) -> dict[str, Any]:
    ed = graph.edges
    props: dict[str, Any] = {"type": ftype, "verified": int(ed["elevator"][e] == TRI_TRUE or ed["escalator"][e] == TRI_TRUE),
                             "handrail": int(ed["handrail"][e]), "ramp": int(ed["ramp"][e]), "tactile": int(ed["tactile"][e])}
    for key, col in (("name", "stop_name"), ("crossing", "crossing"), ("kerb", "kerb")):
        if str(ed[col][e]):
            props[key] = str(ed[col][e])
    steps = _num(ed["step_count"][e], 0)
    if steps is not None:
        props["steps"] = steps
    return props


# ---------------------------------------------------------------- 메모리 스토어 색인
class _EdgeIndex:
    """엣지별 bbox (한 번 계산해 스토어에 붙여 둔다)."""

    def __init__(self, graph: Graph) -> None:
        E = graph.num_edges
        self.min_lat = np.empty(E)
        self.min_lng = np.empty(E)
        self.max_lat = np.empty(E)
        self.max_lng = np.empty(E)
        for e in range(E):
            pts = graph.edge_geometry(e)
            lats = [p[0] for p in pts]
            lngs = [p[1] for p in pts]
            self.min_lat[e], self.max_lat[e] = min(lats), max(lats)
            self.min_lng[e], self.max_lng[e] = min(lngs), max(lngs)

    def query(self, bbox: tuple[float, float, float, float]) -> np.ndarray:
        min_lat, min_lng, max_lat, max_lng = bbox
        return np.flatnonzero((self.max_lat >= min_lat) & (self.min_lat <= max_lat) & (self.max_lng >= min_lng) & (self.min_lng <= max_lng))


_INDEX_LOCK = threading.Lock()


def edge_index(store: MemoryGraphStore) -> _EdgeIndex:
    idx = getattr(store, "_tile_index", None)
    if idx is None:
        with _INDEX_LOCK:   # 첫 타일 요청이 동시에 여러 개 와도 인덱스는 한 번만 만든다
            idx = getattr(store, "_tile_index", None)
            if idx is None:
                idx = _EdgeIndex(store.graph)
                store._tile_index = idx  # type: ignore[attr-defined]
    return idx


# ---------------------------------------------------------------- 타일 생성
def _encode(layers: list[dict[str, Any]], bounds: tuple[float, float, float, float]) -> bytes:
    try:
        return mapbox_vector_tile.encode(layers, default_options={"quantize_bounds": bounds, "extents": EXTENT})
    except TypeError:  # mapbox-vector-tile < 2
        return mapbox_vector_tile.encode(layers, quantize_bounds=bounds, extents=EXTENT)


def render_tile_memory(store: MemoryGraphStore, z: int, x: int, y: int) -> bytes:
    graph = store.graph
    bbox = tile_bbox(z, x, y)
    pad = (bbox[2] - bbox[0]) * 0.05
    padded = (bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad)
    edges = edge_index(store).query(padded)
    kinds = graph.edges["kind"]
    edge_feats: list[dict[str, Any]] = []
    fac_feats: list[dict[str, Any]] = []
    for e in edges:
        if kinds[e] not in SHOWN_EDGE_KINDS:
            continue
        pts = graph.edge_geometry(int(e))
        merc = [lnglat_to_merc(lng, lat) for lat, lng in pts]
        if len(merc) < 2:
            continue
        eid = int(graph.edges["id"][e])
        edge_feats.append({"geometry": LineString(merc), "properties": edge_props(graph, int(e)), "id": eid})
        ftype = facility_type(graph, int(e))
        if ftype:
            line = LineString(merc)
            pt = line.interpolate(0.0 if kinds[e] == "vertical" else 0.5, normalized=True)
            fac_feats.append({"geometry": pt, "properties": facility_props(graph, int(e), ftype), "id": eid})
    nodes = graph.nodes
    in_box = ((nodes["lat"] >= padded[0]) & (nodes["lat"] <= padded[2]) & (nodes["lng"] >= padded[1]) & (nodes["lng"] <= padded[3]))
    stop_feats: list[dict[str, Any]] = []
    for n in np.flatnonzero(in_box):
        kind = str(nodes["kind"][n])
        if kind not in STOP_NODE_KINDS:
            continue
        mx, my = lnglat_to_merc(float(nodes["lng"][n]), float(nodes["lat"][n]))
        stop_feats.append({"geometry": Point(mx, my), "properties": {"kind": kind, "name": str(nodes["name"][n])}, "id": int(nodes["id"][n])})
    if not edge_feats and not stop_feats:
        return b""
    layers = [{"name": "edges", "features": edge_feats}, {"name": "facilities", "features": fac_feats}, {"name": "stops", "features": stop_feats}]
    return _encode([layer for layer in layers if layer["features"]], tile_bounds_merc(z, x, y))


_POSTGIS_TILE_SQL = """
WITH b AS (
    SELECT ST_TileEnvelope(%(z)s, %(x)s, %(y)s) AS g, ST_Transform(ST_TileEnvelope(%(z)s, %(x)s, %(y)s), 4326) AS g4326
),
edges AS (
    SELECT ST_AsMVTGeom(ST_Transform(e.geom, 3857), b.g, %(extent)s, 64, true) AS geom,
           e.id, e.kind, e.mode, round(e.grade_pct::numeric, 1)::float AS grade, round(e.max_grade_pct::numeric, 1)::float AS max_grade,
           e.stairs, e.ramp, e.elevator, e.escalator, round(e.width_m::numeric, 2)::float AS width, e.surface, e.crossing, e.kerb,
           e.tactile, e.handrail, e.indoor, e.route_name, e.stop_name AS name, round(e.step_count::numeric, 0)::float AS steps,
           round(e.length_m::numeric, 1)::float AS length
    FROM graph_edges e, b
    WHERE e.kind IN ('walk', 'link', 'vertical') AND e.geom && b.g4326
),
fac AS (
    SELECT ST_AsMVTGeom(ST_LineInterpolatePoint(ST_Transform(e.geom, 3857), CASE WHEN e.kind = 'vertical' THEN 0.0 ELSE 0.5 END),
                        b.g, %(extent)s, 64, true) AS geom,
           e.id,
           CASE WHEN e.kind = 'vertical' AND e.elevator = 1 THEN 'elevator'
                WHEN e.kind = 'vertical' AND e.escalator = 1 THEN 'escalator'
                WHEN e.kind = 'vertical' AND e.stairs = 1 THEN 'stairs'
                WHEN e.kind = 'vertical' THEN 'vertical'
                WHEN e.stairs = 1 THEN 'stairs'
                WHEN e.kerb IN ('raised', 'rolled') THEN 'kerb'
                ELSE 'crossing' END AS type,
           CASE WHEN e.elevator = 1 OR e.escalator = 1 THEN 1 ELSE 0 END AS verified,
           e.handrail, e.ramp, e.tactile, e.stop_name AS name, e.crossing, e.kerb, round(e.step_count::numeric, 0)::float AS steps
    FROM graph_edges e, b
    WHERE e.geom && b.g4326 AND e.kind IN ('walk', 'link', 'vertical')
      AND (e.stairs = 1 OR e.kind = 'vertical' OR e.kerb IN ('raised', 'rolled') OR e.crossing <> '')
),
stops AS (
    SELECT ST_AsMVTGeom(ST_Transform(n.geom, 3857), b.g, %(extent)s, 64, true) AS geom, n.id, n.kind, n.name
    FROM graph_nodes n, b
    WHERE n.kind IN ('stop', 'platform', 'entrance') AND n.geom && b.g4326
)
SELECT COALESCE((SELECT ST_AsMVT(edges, 'edges', %(extent)s, 'geom', 'id') FROM edges), ''::bytea)
    || COALESCE((SELECT ST_AsMVT(fac, 'facilities', %(extent)s, 'geom', 'id') FROM fac), ''::bytea)
    || COALESCE((SELECT ST_AsMVT(stops, 'stops', %(extent)s, 'geom', 'id') FROM stops), ''::bytea)
"""


def render_tile_postgis(store: Any, z: int, x: int, y: int) -> bytes:
    with store._conn() as conn:
        row = conn.execute(_POSTGIS_TILE_SQL, {"z": z, "x": x, "y": y, "extent": EXTENT}).fetchone()
    return bytes(row[0]) if row and row[0] else b""


def render_tile(store: Any, z: int, x: int, y: int) -> bytes:
    if z < MIN_ZOOM or not valid_tile(z, x, y):
        return b""
    if isinstance(store, MemoryGraphStore):
        return render_tile_memory(store, z, x, y)
    return render_tile_postgis(store, z, x, y)


def tile_meta() -> dict[str, Any]:
    return {
        "minzoom": MIN_ZOOM, "extent": EXTENT,
        "layers": {"edges": "보행 엣지 (경사·계단·턱·폭)", "facilities": "계단·엘리베이터·에스컬레이터·턱·횡단보도", "stops": "정류장·승강장·출입구"},
    }


# ---------------------------------------------------------------- 실시간 그늘
class ShadeBboxError(ValueError):
    pass


def bbox_graph(store: Any, bbox: tuple[float, float, float, float]) -> Graph:
    """bbox 안의 노드와, 양 끝이 모두 안에 있는 보행·연결 엣지만 담은 서브그래프."""
    if isinstance(store, MemoryGraphStore):
        g = store.graph
        min_lat, min_lng, max_lat, max_lng = bbox
        node_mask = (g.nodes["lat"] >= min_lat) & (g.nodes["lat"] <= max_lat) & (g.nodes["lng"] >= min_lng) & (g.nodes["lng"] <= max_lng)
        edge_mask = node_mask[g.src] & node_mask[g.dst] & np.isin(g.edges["kind"], ["walk", "link"])
        return g.subgraph(node_mask, edge_mask)
    return store.bbox_graph(bbox)


def shade_for_bbox(store: Any, bbox: tuple[float, float, float, float], moment: datetime) -> dict[str, Any]:
    min_lat, min_lng, max_lat, max_lng = bbox
    if min_lat >= max_lat or min_lng >= max_lng:
        raise ShadeBboxError("bbox 가 비어 있습니다")
    span = max(haversine_m(min_lat, min_lng, max_lat, min_lng), haversine_m(min_lat, min_lng, min_lat, max_lng))
    if span > SHADE_MAX_SPAN_M:
        raise ShadeBboxError(f"그늘은 한 변 {SHADE_MAX_SPAN_M / 1000:.1f}km 이하 범위에서만 계산합니다 (지도를 더 확대하세요)")
    graph = bbox_graph(store, bbox)
    m = SHADE_BUILDING_MARGIN_DEG
    buildings = store.buildings_in((min_lat - m, min_lng - m, max_lat + m, max_lng + m))
    ratios, info = edge_shade_ratios(graph, buildings, moment)
    kinds = graph.edges["kind"]
    outdoor = graph.edges["indoor"] != TRI_TRUE
    out = {str(int(graph.edges["id"][e])): round(float(ratios[e]), 2) for e in range(graph.num_edges) if kinds[e] in ("walk", "link") and outdoor[e]}
    return {
        "status": info.status, "evaluated_at": info.evaluated_at, "solar_elevation_deg": info.solar_elevation_deg,
        "solar_azimuth_deg": info.solar_azimuth_deg, "building_count": info.building_count, "note": info.note,
        "edges": graph.num_edges, "ratios": out,
    }


# ---------------------------------------------------------------- 타일 LRU 캐시
class TileCache:
    """(z, x, y) → bytes. 그래프는 프로세스 수명 동안 바뀌지 않으므로 TTL 없이 크기만 제한한다."""

    def __init__(self, maxsize: int = 4096) -> None:
        self.maxsize = int(maxsize)
        self._items: OrderedDict[tuple[int, int, int], bytes] = OrderedDict()
        self._lock = threading.Lock()      # 타일 엔드포인트는 스레드풀에서 동시에 돈다
        self.hits = 0
        self.misses = 0

    def get(self, key: tuple[int, int, int]) -> bytes | None:
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                self.hits += 1
                return self._items[key]
            self.misses += 1
            return None

    def put(self, key: tuple[int, int, int], value: bytes) -> None:
        if self.maxsize <= 0:
            return
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.maxsize:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {"maxsize": self.maxsize, "size": len(self._items), "hits": self.hits, "misses": self.misses,
                    "bytes": sum(len(v) for v in self._items.values())}


def render_tile_cached(store: Any, cache: TileCache, z: int, x: int, y: int) -> tuple[bytes, bool]:
    """(타일 바이트, 캐시 적중 여부)."""
    key = (z, x, y)
    data = cache.get(key)
    if data is not None:
        return data, True
    data = render_tile(store, z, x, y)
    cache.put(key, data)
    return data, False


# ---------------------------------------------------------------- 가장 가까운 엣지 (시설 제보 위치 → 엣지)
def _point_segment_m(lat: float, lng: float, a: tuple[float, float], b: tuple[float, float]) -> float:
    """점과 선분 거리(m). 작은 범위이므로 등장방형 근사."""
    k = math.cos(math.radians(lat))
    px, py = lng * k, lat
    ax, ay = a[1] * k, a[0]
    bx, by = b[1] * k, b[0]
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        t = 0.0
    else:
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    qx, qy = ax + t * dx, ay + t * dy
    return math.hypot((px - qx) * 111320.0, (py - qy) * 111320.0)


def nearest_edge(store: Any, lat: float, lng: float, max_distance_m: float = 60.0, kinds: tuple[str, ...] = SHOWN_EDGE_KINDS) -> dict | None:
    """좌표에서 가장 가까운 보행·연결·수직 엣지. 없으면 None."""
    if isinstance(store, MemoryGraphStore):
        g = store.graph
        d = max_distance_m / 111320.0 * 1.5
        cand = edge_index(store).query((lat - d, lng - d, lat + d, lng + d))
        best: tuple[float, int] | None = None
        for e in cand:
            if g.edges["kind"][e] not in kinds:
                continue
            pts = g.edge_geometry(int(e))
            dist = min(_point_segment_m(lat, lng, pts[i], pts[i + 1]) for i in range(len(pts) - 1)) if len(pts) >= 2 else float("inf")
            if dist <= max_distance_m and (best is None or dist < best[0]):
                best = (dist, int(e))
        if best is None:
            return None
        e = best[1]
        return {"edge_id": int(g.edges["id"][e]), "kind": str(g.edges["kind"][e]), "distance_m": round(best[0], 1),
                "stairs": int(g.edges["stairs"][e]), "elevator": int(g.edges["elevator"][e]), "kerb": str(g.edges["kerb"][e]),
                "name": str(g.edges["stop_name"][e])}
    sql = """
        SELECT id, kind, stairs, elevator, kerb, stop_name,
               ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326)::geography) AS d
        FROM graph_edges WHERE kind = ANY(%(kinds)s)
        ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326) LIMIT 1
    """
    with store._conn() as conn:
        row = conn.execute(sql, {"lat": lat, "lng": lng, "kinds": list(kinds)}).fetchone()
    if row is None or row[6] > max_distance_m:
        return None
    return {"edge_id": int(row[0]), "kind": str(row[1]), "distance_m": round(float(row[6]), 1), "stairs": int(row[2]), "elevator": int(row[3]),
            "kerb": str(row[4] or ""), "name": str(row[5] or "")}
