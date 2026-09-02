"""PostGIS 그래프 스토어와 적재기.

- `PostgisGraphStore`: 회랑을 SQL(bbox GIST + 타원 거리 합)로 잘라 `Graph`를 만든다.
- `load_graph()/load_buildings()`: COPY로 그래프·건물을 적재한다.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import psycopg
import shapely

from .corridor import TRANSIT_NODE_KINDS, CorridorSpec
from .model import EDGE_FIELDS, Graph
from .store import SNAP_MAX_M, Building, SnapError, SnappedPoint

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

_EDGE_DB_COLUMNS = [name for name, _, _ in EDGE_FIELDS]  # id, source, target, kind, ...
_NODE_DB_COLUMNS = ["id", "kind", "elevation_m", "name", "station_id"]


def connect(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn)


def init_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


# ---------------------------------------------------------------- 적재
def _point_ewkt(lat: float, lng: float) -> str:
    return f"SRID=4326;POINT({lng:.7f} {lat:.7f})"


def _line_ewkt(coords: Iterable[tuple[float, float]]) -> str:
    parts = ", ".join(f"{lng:.7f} {lat:.7f}" for lat, lng in coords)
    return f"SRID=4326;LINESTRING({parts})"


def _polygon_ewkt(b: Building) -> str:
    def ring(pts):
        pts = list(pts)
        if pts[0] != pts[-1]:
            pts.append(pts[0])
        return "(" + ", ".join(f"{lng:.7f} {lat:.7f}" for lat, lng in pts) + ")"
    rings = [ring(b.footprint)] + [ring(h) for h in b.holes]
    return "SRID=4326;POLYGON(" + ", ".join(rings) + ")"


def _null(v):
    if v is None:
        return None
    if isinstance(v, (float, np.floating)) and math.isnan(v):
        return None
    if isinstance(v, np.generic):
        return v.item()
    return v


def load_graph(conn: psycopg.Connection, graph: Graph, replace: bool = True, meta: dict | None = None) -> dict:
    """그래프를 graph_nodes/graph_edges 에 COPY 한다."""
    init_schema(conn)
    with conn.cursor() as cur:
        if replace:
            cur.execute("TRUNCATE graph_nodes, graph_edges, transit_routes, transit_stops")
        n = graph.nodes
        with cur.copy("COPY graph_nodes (id, kind, geom, elevation_m, name, station_id) FROM STDIN") as copy:
            for i in range(graph.num_nodes):
                copy.write_row((
                    int(n["id"][i]), str(n["kind"][i]), _point_ewkt(float(n["lat"][i]), float(n["lng"][i])),
                    _null(n["elevation_m"][i]), str(n["name"][i]), str(n["station_id"][i]),
                ))
        e = graph.edges
        cols = ", ".join(_EDGE_DB_COLUMNS) + ", geom"
        with cur.copy(f"COPY graph_edges ({cols}) FROM STDIN") as copy:
            for i in range(graph.num_edges):
                row = [_null(e[name][i]) for name in _EDGE_DB_COLUMNS]
                row.append(_line_ewkt(graph.edge_geometry(i)))
                copy.write_row(tuple(row))
        # 노선·정류장 요약
        kinds = e["kind"]
        board = np.nonzero(kinds == "board")[0]
        routes: dict[str, tuple] = {}
        for i in board:
            rid = str(e["route_id"][i])
            if rid and rid not in routes:
                routes[rid] = (rid, str(e["mode"][i]), str(e["route_name"][i]), _null(e["headway_s"][i]), _null(e["low_floor_ratio"][i]))
        cur.executemany(
            "INSERT INTO transit_routes (id, mode, name, headway_s, low_floor_ratio) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
            list(routes.values()),
        )
        stop_idx = np.nonzero(np.isin(n["kind"], ["stop", "platform"]))[0]
        cur.executemany(
            "INSERT INTO transit_stops (id, mode, name, node_id, geom) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
            [(
                str(n["station_id"][i]) or f"node-{int(n['id'][i])}", ("subway" if n["kind"][i] == "platform" else "bus"),
                str(n["name"][i]), int(n["id"][i]), _point_ewkt(float(n["lat"][i]), float(n["lng"][i])),
            ) for i in stop_idx],
        )
        for k, v in (meta or {}).items():
            cur.execute("INSERT INTO graph_meta (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                        (k, json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v))
        cur.execute("INSERT INTO graph_meta (key, value) VALUES ('node_count', %s), ('edge_count', %s) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (str(graph.num_nodes), str(graph.num_edges)))
    conn.commit()
    return {"nodes": graph.num_nodes, "edges": graph.num_edges, "routes": len(routes), "stops": int(len(stop_idx))}


def load_buildings(conn: psycopg.Connection, buildings: list[Building], replace: bool = True, source: str = "") -> int:
    init_schema(conn)
    with conn.cursor() as cur:
        if replace:
            cur.execute("TRUNCATE buildings")
        with cur.copy("COPY buildings (id, height_m, height_source, geom) FROM STDIN") as copy:
            for b in buildings:
                if len(b.footprint) < 3:
                    continue
                copy.write_row((int(b.id), _null(b.height_m), source, _polygon_ewkt(b)))
    conn.commit()
    return len(buildings)


# ---------------------------------------------------------------- 조회
def _rows_to_graph(node_rows: list[tuple], edge_rows: list[tuple]) -> Graph:
    node_ids = np.array([r[0] for r in node_rows], dtype=np.int64)
    nodes = {
        "id": node_ids,
        "kind": np.array([r[1] for r in node_rows], dtype="U12"),
        "lat": np.array([r[2] for r in node_rows], dtype=np.float64),
        "lng": np.array([r[3] for r in node_rows], dtype=np.float64),
        "elevation_m": np.array([np.nan if r[4] is None else r[4] for r in node_rows], dtype=np.float32),
        "name": np.array([r[5] or "" for r in node_rows], dtype="U64"),
        "station_id": np.array([r[6] or "" for r in node_rows], dtype="U32"),
    }
    id_set = set(node_ids.tolist())
    edge_rows = [r for r in edge_rows if r[1] in id_set and r[2] in id_set]
    edges: dict[str, np.ndarray] = {}
    for k, (name, dtype, default) in enumerate(EDGE_FIELDS):
        vals = [r[k] for r in edge_rows]
        if dtype.startswith("U"):
            edges[name] = np.array([("" if v is None else str(v)) for v in vals], dtype=dtype)
        elif dtype.startswith("float"):
            edges[name] = np.array([(np.nan if v is None else v) for v in vals], dtype=dtype)
        else:
            edges[name] = np.array([(default if v is None else v) for v in vals], dtype=dtype)
    geom_offsets = geom_coords = None
    if edge_rows:
        wkbs = [r[len(EDGE_FIELDS)] for r in edge_rows]
        lines = shapely.from_wkb(wkbs)
        coords, index = shapely.get_coordinates(lines, return_index=True)
        counts = np.bincount(index, minlength=len(edge_rows))
        geom_offsets = np.concatenate([[0], np.cumsum(counts)]).astype(np.int64)
        geom_coords = np.column_stack([coords[:, 1], coords[:, 0]])  # (lat, lng)
    else:
        geom_offsets = np.zeros(1, dtype=np.int64)
        geom_coords = np.zeros((0, 2))
    return Graph(nodes, edges, geom_offsets, geom_coords)


_NODE_SELECT = "SELECT id, kind, ST_Y(geom), ST_X(geom), elevation_m, name, station_id FROM graph_nodes"
_EDGE_SELECT = "SELECT " + ", ".join(_EDGE_DB_COLUMNS) + ", ST_AsBinary(geom) FROM graph_edges"


class PostgisGraphStore:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def _conn(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn)

    def corridor(self, spec: CorridorSpec) -> Graph:
        min_lat, min_lng, max_lat, max_lng = spec.bbox(spec.transit_axis_m)
        params = {
            "min_lng": min_lng, "min_lat": min_lat, "max_lng": max_lng, "max_lat": max_lat,
            "olng": spec.origin_lng, "olat": spec.origin_lat, "dlng": spec.dest_lng, "dlat": spec.dest_lat,
            "walk_axis": spec.walk_axis_m, "transit_axis": spec.transit_axis_m, "transit_kinds": list(TRANSIT_NODE_KINDS),
        }
        node_sql = _NODE_SELECT + """
            WHERE geom && ST_MakeEnvelope(%(min_lng)s, %(min_lat)s, %(max_lng)s, %(max_lat)s, 4326)
              AND ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%(olng)s, %(olat)s), 4326)::geography)
                + ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%(dlng)s, %(dlat)s), 4326)::geography)
                <= CASE WHEN kind = ANY(%(transit_kinds)s) THEN %(transit_axis)s ELSE %(walk_axis)s END
        """
        edge_sql = _EDGE_SELECT + " WHERE geom && ST_MakeEnvelope(%(min_lng)s, %(min_lat)s, %(max_lng)s, %(max_lat)s, 4326)"
        with self._conn() as conn:
            node_rows = conn.execute(node_sql, params).fetchall()
            edge_rows = conn.execute(edge_sql, params).fetchall()
        return _rows_to_graph(node_rows, edge_rows)

    def nearest_walk_node(self, lat: float, lng: float, max_distance_m: float = SNAP_MAX_M) -> SnappedPoint:
        sql = """
            SELECT id, ST_Y(geom), ST_X(geom),
                   ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326)::geography) AS d
            FROM graph_nodes WHERE kind = 'walk'
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326) LIMIT 1
        """
        with self._conn() as conn:
            row = conn.execute(sql, {"lat": lat, "lng": lng}).fetchone()
        if row is None or row[3] > max_distance_m:
            dist = "없음" if row is None else f"{row[3]:.0f}m"
            raise SnapError(f"반경 {max_distance_m:.0f}m 안에 보행 노드가 없습니다 (최근접 {dist}).")
        return SnappedPoint(node_id=int(row[0]), node_index_global=-1, lat=float(row[1]), lng=float(row[2]), distance_m=float(row[3]))

    def buildings_in(self, bbox: tuple[float, float, float, float]) -> list[Building]:
        min_lat, min_lng, max_lat, max_lng = bbox
        sql = "SELECT id, height_m, ST_AsBinary(geom) FROM buildings WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)"
        with self._conn() as conn:
            rows = conn.execute(sql, (min_lng, min_lat, max_lng, max_lat)).fetchall()
        out: list[Building] = []
        for bid, height, wkb in rows:
            poly = shapely.from_wkb(wkb)
            if poly.geom_type != "Polygon":
                continue
            footprint = [(float(y), float(x)) for x, y in poly.exterior.coords]
            holes = [[(float(y), float(x)) for x, y in ring.coords] for ring in poly.interiors]
            out.append(Building(id=int(bid), height_m=(None if height is None else float(height)), footprint=footprint, holes=holes))
        return out

    def load_full(self) -> Graph:
        with self._conn() as conn:
            node_rows = conn.execute(_NODE_SELECT).fetchall()
            edge_rows = conn.execute(_EDGE_SELECT).fetchall()
        return _rows_to_graph(node_rows, edge_rows)

    def load_all_buildings(self) -> list[Building]:
        return self.buildings_in((-90.0, -180.0, 90.0, 180.0))

    def describe(self) -> dict:
        with self._conn() as conn:
            meta = dict(conn.execute("SELECT key, value FROM graph_meta").fetchall())
            buildings = conn.execute("SELECT count(*) FROM buildings").fetchone()[0]
        return {"source": "postgis", "nodes": int(meta.get("node_count", 0)), "edges": int(meta.get("edge_count", 0)),
                "buildings": int(buildings), "meta": meta}
