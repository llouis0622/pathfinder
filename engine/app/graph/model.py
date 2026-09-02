"""멀티모달 그래프의 메모리 표현.

노드·엣지 속성을 numpy 배열로 들고, CSR 인접 구조(out/in)를 만든다.
불리언 속성은 3진(tri-state)으로 저장한다: 1=True, 0=False, -1=미상.
문자열 속성의 미상은 빈 문자열, 실수 속성의 미상은 NaN이다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .geo import haversine_m

TRI_TRUE, TRI_FALSE, TRI_UNKNOWN = 1, 0, -1

NODE_KINDS = ("walk", "stop", "route_stop", "entrance", "platform")
EDGE_KINDS = ("walk", "link", "board", "ride", "alight", "vertical", "transfer")
MODES = ("", "walk", "subway", "bus")

# (필드명, dtype, 기본값). npz 입출력·서브그래프·PostGIS 적재가 이 표를 공유한다.
NODE_FIELDS: tuple[tuple[str, str, Any], ...] = (
    ("id", "int64", 0),
    ("kind", "U12", "walk"),
    ("lat", "float64", 0.0),
    ("lng", "float64", 0.0),
    ("elevation_m", "float32", np.nan),
    ("name", "U64", ""),
    ("station_id", "U32", ""),
)

EDGE_FIELDS: tuple[tuple[str, str, Any], ...] = (
    ("id", "int64", 0),
    ("source", "int64", 0),
    ("target", "int64", 0),
    ("kind", "U10", "walk"),
    ("mode", "U8", ""),
    ("length_m", "float32", 0.0),
    ("time_s", "float32", np.nan),
    ("grade_pct", "float32", np.nan),
    ("stairs", "int8", TRI_FALSE),
    ("step_count", "float32", np.nan),
    ("ramp", "int8", TRI_UNKNOWN),
    ("elevator", "int8", TRI_UNKNOWN),
    ("escalator", "int8", TRI_UNKNOWN),
    ("surface", "U20", ""),
    ("width_m", "float32", np.nan),
    ("tactile", "int8", TRI_UNKNOWN),
    ("handrail", "int8", TRI_UNKNOWN),
    ("crossing", "U20", ""),
    ("kerb", "U16", ""),
    ("lit", "int8", TRI_UNKNOWN),
    ("indoor", "int8", TRI_FALSE),
    ("route_id", "U32", ""),
    ("route_name", "U32", ""),
    ("headway_s", "float32", np.nan),
    ("low_floor_ratio", "float32", np.nan),
    ("stop_name", "U64", ""),
)

_BOOL_TRI_FIELDS = {"stairs", "ramp", "elevator", "escalator", "tactile", "handrail", "lit", "indoor"}


def tri(value: Any) -> int:
    """파이썬 값 → 3진 정수."""
    if value is None:
        return TRI_UNKNOWN
    if isinstance(value, (bool, np.bool_)):
        return TRI_TRUE if value else TRI_FALSE
    if isinstance(value, (int, np.integer)):
        return int(value) if value in (-1, 0, 1) else (TRI_TRUE if value else TRI_FALSE)
    if isinstance(value, float):
        if np.isnan(value):
            return TRI_UNKNOWN
        return TRI_TRUE if value else TRI_FALSE
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("yes", "true", "1", "y"):
            return TRI_TRUE
        if v in ("no", "false", "0", "n"):
            return TRI_FALSE
        return TRI_UNKNOWN
    return TRI_UNKNOWN


def tri_to_optional(value: int) -> bool | None:
    if value == TRI_TRUE:
        return True
    if value == TRI_FALSE:
        return False
    return None


def _column(records: list[dict], name: str, dtype: str, default: Any) -> np.ndarray:
    if name in _BOOL_TRI_FIELDS:
        return np.array([tri(r.get(name, default)) for r in records], dtype=dtype)
    values = []
    for r in records:
        v = r.get(name, default)
        if v is None:
            v = default
        values.append(v)
    if dtype.startswith("U"):
        return np.array([("" if v is None else str(v)) for v in values], dtype=dtype)
    return np.array(values, dtype=dtype)


@dataclass
class Graph:
    """노드·엣지 배열과 CSR 인접 구조."""

    nodes: dict[str, np.ndarray]
    edges: dict[str, np.ndarray]
    # 엣지 표시용 좌표: geom_coords[(geom_offsets[e]):(geom_offsets[e+1])] = [[lat,lng],...]
    geom_offsets: np.ndarray | None = None
    geom_coords: np.ndarray | None = None
    # 파생 구조
    src: np.ndarray = field(init=False)
    dst: np.ndarray = field(init=False)
    out_indptr: np.ndarray = field(init=False)
    out_edges: np.ndarray = field(init=False)
    in_indptr: np.ndarray = field(init=False)
    in_edges: np.ndarray = field(init=False)
    id_to_index: dict[int, int] = field(init=False)

    def __post_init__(self) -> None:
        self._validate()
        self._build_index()

    # ---------- 생성 ----------
    @classmethod
    def from_records(cls, nodes: Iterable[dict], edges: Iterable[dict],
                     edge_geoms: dict[int, list[tuple[float, float]]] | None = None) -> "Graph":
        node_records = list(nodes)
        edge_records = list(edges)
        node_arrays = {name: _column(node_records, name, dtype, default) for name, dtype, default in NODE_FIELDS}
        edge_arrays = {name: _column(edge_records, name, dtype, default) for name, dtype, default in EDGE_FIELDS}
        geom_offsets = geom_coords = None
        if edge_geoms:
            offsets = [0]
            coords: list[tuple[float, float]] = []
            for eid in edge_arrays["id"]:
                pts = edge_geoms.get(int(eid))
                if pts:
                    coords.extend((float(p[0]), float(p[1])) for p in pts)
                offsets.append(len(coords))
            geom_offsets = np.asarray(offsets, dtype=np.int64)
            geom_coords = np.asarray(coords, dtype=np.float64).reshape(-1, 2)
        return cls(node_arrays, edge_arrays, geom_offsets, geom_coords)

    @classmethod
    def empty(cls) -> "Graph":
        return cls.from_records([], [])

    # ---------- 검증·인덱스 ----------
    def _validate(self) -> None:
        for name, dtype, default in NODE_FIELDS:
            if name not in self.nodes:
                self.nodes[name] = np.full(self.num_nodes, default, dtype=dtype)
        for name, dtype, default in EDGE_FIELDS:
            if name not in self.edges:
                self.edges[name] = np.full(self.num_edges, default, dtype=dtype)
        if self.num_edges:
            bad = self.edges["length_m"] < 0
            if bad.any():
                raise ValueError("음수 길이 엣지가 있습니다.")

    def _build_index(self) -> None:
        ids = self.nodes["id"]
        self.id_to_index = {int(i): k for k, i in enumerate(ids)}
        if len(self.id_to_index) != len(ids):
            raise ValueError("노드 id가 중복됩니다.")
        n = self.num_nodes
        try:
            self.src = np.fromiter((self.id_to_index[int(s)] for s in self.edges["source"]), dtype=np.int64, count=self.num_edges)
            self.dst = np.fromiter((self.id_to_index[int(t)] for t in self.edges["target"]), dtype=np.int64, count=self.num_edges)
        except KeyError as exc:
            raise ValueError(f"엣지가 존재하지 않는 노드를 참조합니다: {exc}") from exc
        order = np.argsort(self.src, kind="stable")
        self.out_edges = order.astype(np.int64)
        self.out_indptr = np.zeros(n + 1, dtype=np.int64)
        np.add.at(self.out_indptr, self.src + 1, 1)
        np.cumsum(self.out_indptr, out=self.out_indptr)
        order_in = np.argsort(self.dst, kind="stable")
        self.in_edges = order_in.astype(np.int64)
        self.in_indptr = np.zeros(n + 1, dtype=np.int64)
        np.add.at(self.in_indptr, self.dst + 1, 1)
        np.cumsum(self.in_indptr, out=self.in_indptr)

    # ---------- 조회 ----------
    @property
    def num_nodes(self) -> int:
        return int(len(self.nodes["id"]))

    @property
    def num_edges(self) -> int:
        return int(len(self.edges["id"]))

    def out_edge_indices(self, node_index: int) -> np.ndarray:
        return self.out_edges[self.out_indptr[node_index]:self.out_indptr[node_index + 1]]

    def in_edge_indices(self, node_index: int) -> np.ndarray:
        return self.in_edges[self.in_indptr[node_index]:self.in_indptr[node_index + 1]]

    def edge_geometry(self, edge_index: int) -> list[tuple[float, float]]:
        """엣지 표시 좌표 [(lat, lng), ...]. 저장된 도형이 없으면 양 끝 노드 직선."""
        if self.geom_offsets is not None and self.geom_coords is not None:
            a, b = self.geom_offsets[edge_index], self.geom_offsets[edge_index + 1]
            if b - a >= 2:
                return [(float(p[0]), float(p[1])) for p in self.geom_coords[a:b]]
        u, v = self.src[edge_index], self.dst[edge_index]
        return [
            (float(self.nodes["lat"][u]), float(self.nodes["lng"][u])),
            (float(self.nodes["lat"][v]), float(self.nodes["lng"][v])),
        ]

    def edge_record(self, edge_index: int) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name, _, _ in EDGE_FIELDS:
            v = self.edges[name][edge_index]
            if name in _BOOL_TRI_FIELDS:
                out[name] = tri_to_optional(int(v))
            elif isinstance(v, np.floating):
                out[name] = None if np.isnan(v) else float(v)
            elif isinstance(v, np.integer):
                out[name] = int(v)
            else:
                out[name] = str(v)
        return out

    def node_record(self, node_index: int) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name, _, _ in NODE_FIELDS:
            v = self.nodes[name][node_index]
            if isinstance(v, np.floating):
                out[name] = None if np.isnan(v) else float(v)
            elif isinstance(v, np.integer):
                out[name] = int(v)
            else:
                out[name] = str(v)
        return out

    def straight_lengths(self) -> np.ndarray:
        return haversine_m(
            self.nodes["lat"][self.src], self.nodes["lng"][self.src],
            self.nodes["lat"][self.dst], self.nodes["lng"][self.dst],
        )

    # ---------- 변환 ----------
    def subgraph(self, node_mask: np.ndarray, edge_mask: np.ndarray | None = None) -> "Graph":
        """노드 마스크(및 선택적 엣지 마스크)로 서브그래프를 만든다. 양 끝 노드가 모두 포함된 엣지만 남긴다."""
        keep_edges = node_mask[self.src] & node_mask[self.dst]
        if edge_mask is not None:
            keep_edges &= edge_mask
        nodes = {k: v[node_mask] for k, v in self.nodes.items()}
        edges = {k: v[keep_edges] for k, v in self.edges.items()}
        geom_offsets = geom_coords = None
        if self.geom_offsets is not None and self.geom_coords is not None:
            kept = np.nonzero(keep_edges)[0]
            lengths = self.geom_offsets[kept + 1] - self.geom_offsets[kept]
            geom_offsets = np.concatenate([[0], np.cumsum(lengths)]).astype(np.int64)
            pieces = [self.geom_coords[self.geom_offsets[e]:self.geom_offsets[e + 1]] for e in kept]
            geom_coords = np.concatenate(pieces).reshape(-1, 2) if pieces else np.zeros((0, 2))
        return Graph(nodes, edges, geom_offsets, geom_coords)

    # ---------- 파일 입출력 ----------
    def save_npz(self, path: str | Path) -> None:
        payload: dict[str, np.ndarray] = {}
        for k, v in self.nodes.items():
            payload[f"n__{k}"] = v
        for k, v in self.edges.items():
            payload[f"e__{k}"] = v
        if self.geom_offsets is not None and self.geom_coords is not None:
            payload["geom_offsets"] = self.geom_offsets
            payload["geom_coords"] = self.geom_coords
        np.savez_compressed(path, **payload)

    @classmethod
    def load_npz(cls, path: str | Path) -> "Graph":
        with np.load(path, allow_pickle=False) as data:
            nodes = {k[3:]: data[k] for k in data.files if k.startswith("n__")}
            edges = {k[3:]: data[k] for k in data.files if k.startswith("e__")}
            geom_offsets = data["geom_offsets"] if "geom_offsets" in data.files else None
            geom_coords = data["geom_coords"] if "geom_coords" in data.files else None
        return cls(nodes, edges, geom_offsets, geom_coords)
