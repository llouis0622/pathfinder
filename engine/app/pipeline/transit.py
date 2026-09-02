"""대중교통 노선 명세(TransitSpec) → 그래프. 지하철·버스 빌더가 공유한다."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..graph.geo import haversine_m
from ..graph.model import Graph

SUBWAY_NODE_BASE = 8_000_000_000_000
BUS_NODE_BASE = 8_100_000_000_000


@dataclass(frozen=True)
class TransitStop:
    id: str
    name: str
    lat: float
    lng: float


@dataclass
class TransitRoute:
    id: str
    name: str
    mode: str                       # subway | bus
    stops: list[TransitStop]
    headway_s: float | None = None
    low_floor_ratio: float | None = None
    color: str = ""
    travel_s: list[float | None] = field(default_factory=list)   # len(stops)-1, 없으면 거리/속도


@dataclass
class TransitSpec:
    routes: list[TransitRoute]
    mode: str
    stop_kind: str                  # stop(버스) | platform(지하철)
    speed_mps: float
    dwell_s: float

    def unique_stops(self) -> dict[str, TransitStop]:
        out: dict[str, TransitStop] = {}
        for r in self.routes:
            for s in r.stops:
                out.setdefault(s.id, s)
        return out


@dataclass
class TransitBuild:
    graph: Graph
    stop_node_ids: dict[str, int]
    next_node_id: int
    routes: int
    stops: int


def build_transit_graph(spec: TransitSpec, node_id_base: int, edge_id_base: int = 1) -> TransitBuild:
    nodes: list[dict] = []
    edges: list[dict] = []
    next_node = node_id_base
    next_edge = edge_id_base
    stop_node: dict[str, int] = {}
    indoor = spec.mode == "subway"
    for sid, s in spec.unique_stops().items():
        stop_node[sid] = next_node
        nodes.append({"id": next_node, "kind": spec.stop_kind, "lat": s.lat, "lng": s.lng, "name": s.name, "station_id": sid})
        next_node += 1
    for r in spec.routes:
        if len(r.stops) < 2:
            continue
        rs_ids: list[int] = []
        for s in r.stops:
            rs = next_node
            next_node += 1
            rs_ids.append(rs)
            nodes.append({"id": rs, "kind": "route_stop", "lat": s.lat, "lng": s.lng, "name": s.name, "station_id": s.id})
            edges.append({"id": next_edge, "source": stop_node[s.id], "target": rs, "kind": "board", "mode": r.mode, "length_m": 0.0,
                          "route_id": r.id, "route_name": r.name, "headway_s": r.headway_s, "low_floor_ratio": r.low_floor_ratio,
                          "indoor": indoor, "stop_name": s.name})
            next_edge += 1
            edges.append({"id": next_edge, "source": rs, "target": stop_node[s.id], "kind": "alight", "mode": r.mode, "length_m": 0.0,
                          "route_id": r.id, "route_name": r.name, "indoor": indoor, "stop_name": s.name})
            next_edge += 1
        for k, (a, b) in enumerate(zip(r.stops, r.stops[1:])):
            L = float(haversine_m(a.lat, a.lng, b.lat, b.lng))
            t = r.travel_s[k] if k < len(r.travel_s) and r.travel_s[k] is not None else L / spec.speed_mps + spec.dwell_s
            edges.append({"id": next_edge, "source": rs_ids[k], "target": rs_ids[k + 1], "kind": "ride", "mode": r.mode, "length_m": L,
                          "time_s": float(t), "route_id": r.id, "route_name": r.name, "indoor": True})
            next_edge += 1
    graph = Graph.from_records(nodes, edges)
    return TransitBuild(graph, stop_node, next_node, len(spec.routes), len(stop_node))
