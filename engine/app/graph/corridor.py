"""회랑(corridor) 추출: 출발·도착을 초점으로 하는 타원 안의 노드만 남긴다."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .geo import haversine_m
from .model import Graph

WALK_FACTOR = 1.4
WALK_EXTRA_M = 1500.0
TRANSIT_FACTOR = 2.0
TRANSIT_EXTRA_M = 4000.0
TRANSIT_NODE_KINDS = ("stop", "route_stop", "entrance", "platform")


@dataclass(frozen=True)
class CorridorSpec:
    origin_lat: float
    origin_lng: float
    dest_lat: float
    dest_lng: float
    walk_factor: float = WALK_FACTOR
    walk_extra_m: float = WALK_EXTRA_M
    transit_factor: float = TRANSIT_FACTOR
    transit_extra_m: float = TRANSIT_EXTRA_M

    @property
    def direct_m(self) -> float:
        return float(haversine_m(self.origin_lat, self.origin_lng, self.dest_lat, self.dest_lng))

    @property
    def walk_axis_m(self) -> float:
        d = self.direct_m
        return max(self.walk_factor * d, d + self.walk_extra_m)

    @property
    def transit_axis_m(self) -> float:
        d = self.direct_m
        return max(self.transit_factor * d, d + self.transit_extra_m)

    def bbox(self, axis_m: float | None = None) -> tuple[float, float, float, float]:
        """타원을 감싸는 (min_lat, min_lng, max_lat, max_lng)."""
        a = (axis_m or self.transit_axis_m) / 2.0
        c_lat = (self.origin_lat + self.dest_lat) / 2.0
        c_lng = (self.origin_lng + self.dest_lng) / 2.0
        dlat = a / 110_540.0
        dlng = a / (111_320.0 * max(np.cos(np.radians(c_lat)), 1e-6))
        return (c_lat - dlat, c_lng - dlng, c_lat + dlat, c_lng + dlng)


def corridor_mask(graph: Graph, spec: CorridorSpec) -> np.ndarray:
    """그래프 노드에 대한 회랑 포함 마스크. 대중교통 노드는 넓은 타원을 쓴다."""
    lat = graph.nodes["lat"]
    lng = graph.nodes["lng"]
    total = haversine_m(lat, lng, spec.origin_lat, spec.origin_lng) + haversine_m(lat, lng, spec.dest_lat, spec.dest_lng)
    is_transit = np.isin(graph.nodes["kind"], TRANSIT_NODE_KINDS)
    axis = np.where(is_transit, spec.transit_axis_m, spec.walk_axis_m)
    return total <= axis


def extract_corridor(graph: Graph, spec: CorridorSpec) -> Graph:
    return graph.subgraph(corridor_mask(graph, spec))
