"""그래프 스토어 인터페이스와 메모리 구현.

`GraphStore`는 회랑 서브그래프·최근접 보행 노드·회랑 안 건물을 제공한다.
운영은 `PostgisGraphStore`(postgis.py), 개발·테스트는 `MemoryGraphStore`를 쓴다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np
from scipy.spatial import cKDTree

from .corridor import CorridorSpec, extract_corridor
from .geo import project_local
from .model import Graph

SNAP_MAX_M = 300.0


@dataclass(frozen=True)
class Building:
    id: int
    height_m: float | None
    footprint: list[tuple[float, float]]           # [(lat, lng), ...] 외곽
    holes: list[list[tuple[float, float]]] = field(default_factory=list)


@dataclass(frozen=True)
class SnappedPoint:
    node_id: int
    node_index_global: int
    lat: float
    lng: float
    distance_m: float


class SnapError(ValueError):
    pass


class GraphStore(Protocol):
    def corridor(self, spec: CorridorSpec) -> Graph: ...
    def nearest_walk_node(self, lat: float, lng: float, max_distance_m: float = SNAP_MAX_M) -> SnappedPoint: ...
    def buildings_in(self, bbox: tuple[float, float, float, float]) -> list[Building]: ...
    def describe(self) -> dict: ...


class MemoryGraphStore:
    """전체 그래프를 메모리에 들고 회랑을 numpy 마스크로 잘라낸다."""

    def __init__(self, graph: Graph, buildings: list[Building] | None = None, source: str = "memory") -> None:
        self.graph = graph
        self.buildings = list(buildings or [])
        self.source = source
        self._walk_idx = np.nonzero(graph.nodes["kind"] == "walk")[0]
        if len(self._walk_idx) == 0:
            raise ValueError("보행 노드가 없는 그래프입니다.")
        self._ref_lat = float(np.mean(graph.nodes["lat"][self._walk_idx]))
        self._ref_lng = float(np.mean(graph.nodes["lng"][self._walk_idx]))
        x, y = project_local(graph.nodes["lat"][self._walk_idx], graph.nodes["lng"][self._walk_idx], self._ref_lat, self._ref_lng)
        self._tree = cKDTree(np.column_stack([x, y]))
        if self.buildings:
            centroids = np.array([[np.mean([p[0] for p in b.footprint]), np.mean([p[1] for p in b.footprint])] for b in self.buildings])
            self._building_centroids = centroids
        else:
            self._building_centroids = np.zeros((0, 2))

    @classmethod
    def from_npz(cls, path: str | Path, buildings_path: str | Path | None = None) -> "MemoryGraphStore":
        graph = Graph.load_npz(path)
        buildings: list[Building] = []
        if buildings_path and Path(buildings_path).is_file():
            buildings = load_buildings_json(buildings_path)
        return cls(graph, buildings, source=str(path))

    def corridor(self, spec: CorridorSpec) -> Graph:
        return extract_corridor(self.graph, spec)

    def nearest_walk_node(self, lat: float, lng: float, max_distance_m: float = SNAP_MAX_M) -> SnappedPoint:
        x, y = project_local(lat, lng, self._ref_lat, self._ref_lng)
        dist, pos = self._tree.query([float(x), float(y)])
        if not np.isfinite(dist) or dist > max_distance_m:
            raise SnapError(f"반경 {max_distance_m:.0f}m 안에 보행 노드가 없습니다 (최근접 {dist:.0f}m).")
        gidx = int(self._walk_idx[pos])
        return SnappedPoint(
            node_id=int(self.graph.nodes["id"][gidx]),
            node_index_global=gidx,
            lat=float(self.graph.nodes["lat"][gidx]),
            lng=float(self.graph.nodes["lng"][gidx]),
            distance_m=float(dist),
        )

    def buildings_in(self, bbox: tuple[float, float, float, float]) -> list[Building]:
        if not self.buildings:
            return []
        min_lat, min_lng, max_lat, max_lng = bbox
        c = self._building_centroids
        m = (c[:, 0] >= min_lat) & (c[:, 0] <= max_lat) & (c[:, 1] >= min_lng) & (c[:, 1] <= max_lng)
        return [b for b, keep in zip(self.buildings, m) if keep]

    def describe(self) -> dict:
        return {
            "source": self.source,
            "nodes": self.graph.num_nodes,
            "edges": self.graph.num_edges,
            "buildings": len(self.buildings),
        }


def load_buildings_json(path: str | Path) -> list[Building]:
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out: list[Building] = []
    for i, b in enumerate(data.get("buildings", data if isinstance(data, list) else [])):
        fp = [(float(p[0]), float(p[1])) for p in b["footprint"]]
        holes = [[(float(p[0]), float(p[1])) for p in ring] for ring in b.get("holes", [])]
        h = b.get("height_m")
        out.append(Building(id=int(b.get("id", i)), height_m=(float(h) if h is not None else None), footprint=fp, holes=holes))
    return out


def save_buildings_json(path: str | Path, buildings: list[Building]) -> None:
    import json

    payload = {"buildings": [
        {"id": b.id, "height_m": b.height_m, "footprint": [[p[0], p[1]] for p in b.footprint],
         "holes": [[[p[0], p[1]] for p in ring] for ring in b.holes]}
        for b in buildings
    ]}
    Path(path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
