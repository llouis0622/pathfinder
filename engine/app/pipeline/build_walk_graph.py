"""OSM PBF → 보행 그래프.

    python -m app.pipeline.build_walk_graph --pbf ../data/raw/south-korea-latest.osm.pbf --out ../data/build/walk.npz

pyrosm 으로 부산 경계 안 walking 네트워크를 읽고, 태그를 엣지 속성으로 파생한 뒤 양방향 엣지를 만든다.
`build_from_frames()` 는 pyrosm 이 돌려주는 것과 같은 열을 가진 DataFrame 을 받으므로 테스트에서 합성 입력으로 검증한다.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..graph.geo import polyline_length_m
from ..graph.merge import largest_component
from ..graph.model import Graph
from .osm_tags import WALK_TAGS, derive_walk_attrs, is_walkable

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DEFAULT_BOUNDARY = DATA_DIR / "boundary" / "busan_hangjeongdong.geojson"
DEFAULT_UNRAMPED = DATA_DIR / "osm" / "busan_osm_steps_ramp_no_20260724.geojson"


@dataclass
class WalkReport:
    source_nodes: int
    source_edges: int
    nodes: int
    edges: int
    dropped_unwalkable: int
    unramped_applied: int
    removed_disconnected: int


def load_unramped_way_ids(path: Path | None) -> set[int]:
    if not path or not Path(path).is_file():
        return set()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    ids: set[int] = set()
    for f in data.get("features", []):
        props = f.get("properties") or {}
        way = props.get("osmWayId") or props.get("osm_way_id") or props.get("id")
        if way is not None:
            try:
                ids.add(int(way))
            except (TypeError, ValueError):
                continue
    return ids


def _geom_coords(geom: Any, u_lat: float, u_lng: float, v_lat: float, v_lng: float) -> list[tuple[float, float]]:
    if geom is not None and hasattr(geom, "coords"):
        pts = [(float(y), float(x)) for x, y in geom.coords]
        if len(pts) >= 2:
            # 방향이 u→v 와 맞는지 확인
            if (abs(pts[0][0] - u_lat) + abs(pts[0][1] - u_lng)) > (abs(pts[-1][0] - u_lat) + abs(pts[-1][1] - u_lng)):
                pts.reverse()
            return pts
    return [(u_lat, u_lng), (v_lat, v_lng)]


def build_from_frames(nodes_df, edges_df, unramped_way_ids: set[int] | None = None, keep_largest: bool = True) -> tuple[Graph, WalkReport]:
    """nodes_df: id, lat, lon ; edges_df: u, v, id(way), geometry(선택), 태그 열들."""
    unramped_way_ids = unramped_way_ids or set()
    node_pos = {int(r.id): (float(r.lat), float(r.lon)) for r in nodes_df[["id", "lat", "lon"]].itertuples(index=False)}
    tag_cols = [c for c in WALK_TAGS if c in edges_df.columns]
    has_geom = "geometry" in edges_df.columns
    node_records: dict[int, dict] = {}
    edge_records: list[dict] = []
    geoms: dict[int, list[tuple[float, float]]] = {}
    dropped = unramped = 0
    next_id = 1
    for row in edges_df.itertuples(index=False):
        u, v = int(row.u), int(row.v)
        if u not in node_pos or v not in node_pos or u == v:
            continue
        tags = {c: getattr(row, c) for c in tag_cols}
        if not is_walkable(tags):
            dropped += 1
            continue
        attrs = derive_walk_attrs(tags)
        way_id = int(getattr(row, "id", 0) or 0) if hasattr(row, "id") else 0
        if attrs["stairs"] and way_id in unramped_way_ids:
            attrs["ramp"] = False
            unramped += 1
        (u_lat, u_lng), (v_lat, v_lng) = node_pos[u], node_pos[v]
        pts = _geom_coords(getattr(row, "geometry", None) if has_geom else None, u_lat, u_lng, v_lat, v_lng)
        length = float(getattr(row, "length", 0) or 0) or polyline_length_m(pts)
        if length <= 0:
            continue
        for a, b, geom in ((u, v, pts), (v, u, list(reversed(pts)))):
            rec = {"id": next_id, "source": a, "target": b, "length_m": length, **attrs}
            edge_records.append(rec)
            geoms[next_id] = geom
            next_id += 1
        for nid in (u, v):
            if nid not in node_records:
                lat, lng = node_pos[nid]
                node_records[nid] = {"id": nid, "kind": "walk", "lat": lat, "lng": lng}
    graph = Graph.from_records(list(node_records.values()), edge_records, geoms)
    removed = 0
    if keep_largest and graph.num_nodes:
        graph, removed = largest_component(graph)
    return graph, WalkReport(len(node_pos), len(edges_df), graph.num_nodes, graph.num_edges, dropped, unramped, removed)


def build_from_pbf(pbf_path: Path, boundary_path: Path = DEFAULT_BOUNDARY, unramped_path: Path | None = DEFAULT_UNRAMPED,
                   keep_largest: bool = True) -> tuple[Graph, WalkReport]:
    import geopandas as gpd
    from pyrosm import OSM

    boundary = gpd.read_file(boundary_path).to_crs("EPSG:4326").geometry.union_all()
    osm = OSM(str(pbf_path), bounding_box=boundary, keep_metadata=False)
    nodes, edges = osm.get_network(network_type="walking", nodes=True, extra_attributes=[t for t in WALK_TAGS])
    if nodes is None or edges is None or nodes.empty or edges.empty:
        raise ValueError("보행 네트워크를 추출하지 못했습니다.")
    edges = edges.to_crs("EPSG:4326") if edges.crs is not None else edges
    return build_from_frames(nodes, edges, load_unramped_way_ids(unramped_path), keep_largest=keep_largest)


def main() -> None:
    parser = argparse.ArgumentParser(description="OSM PBF → 부산 보행 그래프")
    parser.add_argument("--pbf", type=Path, required=True)
    parser.add_argument("--boundary", type=Path, default=DEFAULT_BOUNDARY)
    parser.add_argument("--unramped", type=Path, default=DEFAULT_UNRAMPED)
    parser.add_argument("--out", type=Path, default=Path("../data/build/walk.npz"))
    args = parser.parse_args()
    graph, report = build_from_pbf(args.pbf, args.boundary, args.unramped)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    graph.save_npz(args.out)
    print(json.dumps(report.__dict__, ensure_ascii=False), "->", args.out)


if __name__ == "__main__":
    main()

__all__ = ["build_from_frames", "build_from_pbf", "load_unramped_way_ids", "WalkReport", "np"]
