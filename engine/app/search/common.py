"""탐색 알고리즘이 공유하는 경량 인접 구조와 경로 유틸리티."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..graph.model import Graph


@dataclass
class Adjacency:
    """비용이 유한한 엣지만 담은 파이썬 리스트 기반 인접 구조 (개미·GA의 핫 루프용)."""

    out: list[list[tuple[int, int]]]      # out[u] = [(edge_idx, v), ...]
    edge_lookup: dict[tuple[int, int], int]  # (u, v) -> 최소 비용 엣지
    cost: list[float]
    src: list[int]
    dst: list[int]

    @classmethod
    def build(cls, graph: Graph, cost: np.ndarray) -> "Adjacency":
        n = graph.num_nodes
        out: list[list[tuple[int, int]]] = [[] for _ in range(n)]
        lookup: dict[tuple[int, int], int] = {}
        src = graph.src.tolist()
        dst = graph.dst.tolist()
        cost_list = cost.tolist()
        for e in range(graph.num_edges):
            c = cost_list[e]
            if c == float("inf") or c != c:
                continue
            u, v = src[e], dst[e]
            out[u].append((e, v))
            key = (u, v)
            prev = lookup.get(key)
            if prev is None or cost_list[prev] > c:
                lookup[key] = e
        return cls(out, lookup, cost_list, src, dst)

    def path_cost(self, edge_path: list[int]) -> float:
        return float(sum(self.cost[e] for e in edge_path))


def edges_to_nodes(edge_path: list[int], adj: Adjacency, start: int) -> list[int]:
    nodes = [start]
    for e in edge_path:
        nodes.append(adj.dst[e])
    return nodes


def nodes_to_edges(node_path: list[int], adj: Adjacency) -> list[int] | None:
    """노드 열 → 엣지 열. 연결 엣지가 없으면 None."""
    edges: list[int] = []
    for u, v in zip(node_path, node_path[1:]):
        e = adj.edge_lookup.get((u, v))
        if e is None:
            return None
        edges.append(e)
    return edges


def remove_loops(node_path: list[int]) -> list[int]:
    """반복 노드가 있으면 첫 등장~마지막 등장 사이를 잘라 단순 경로로 만든다."""
    result: list[int] = []
    position: dict[int, int] = {}
    for node in node_path:
        if node in position:
            cut = position[node]
            for removed in result[cut + 1:]:
                position.pop(removed, None)
            del result[cut + 1:]
        else:
            position[node] = len(result)
            result.append(node)
    return result


def path_key(edge_path: list[int]) -> tuple[int, ...]:
    return tuple(edge_path)
