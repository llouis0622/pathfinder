"""Dijkstra: 전역(scipy, cost-to-go용)과 목표 지향(파이썬 heapq, 조기 종료·노드 금지·가중치 교란 지원)."""
from __future__ import annotations

import heapq
import random

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra as _sp_dijkstra

from ..graph.model import Graph
from .common import Adjacency


def cost_to_go(graph: Graph, cost: np.ndarray, target_index: int) -> np.ndarray:
    """모든 노드에서 target까지의 최소 비용 h(v). 도달 불가는 inf."""
    n = graph.num_nodes
    if n == 0:
        return np.zeros(0)
    finite = np.isfinite(cost)
    if not finite.any():
        h = np.full(n, np.inf)
        h[target_index] = 0.0
        return h
    src = graph.src[finite]
    dst = graph.dst[finite]
    w = cost[finite]
    # 병렬 엣지는 최소 비용만 남긴다 (coo→csr 은 중복을 합산하므로)
    order = np.lexsort((w, dst, src))
    src, dst, w = src[order], dst[order], w[order]
    keep = np.ones(len(src), dtype=bool)
    keep[1:] = (src[1:] != src[:-1]) | (dst[1:] != dst[:-1])
    src, dst, w = src[keep], dst[keep], w[keep]
    # 역방향: target → 모든 노드 = 전치 그래프에서의 최단
    matrix = coo_matrix((w, (dst, src)), shape=(n, n)).tocsr()
    dist = _sp_dijkstra(matrix, directed=True, indices=target_index)
    return np.asarray(dist, dtype=np.float64)


def shortest_path(
    adj: Adjacency,
    source: int,
    target: int,
    *,
    forbidden: bytearray | None = None,
    edge_factor: dict[int, float] | None = None,
    jitter: tuple[float, float] | None = None,
    rng: random.Random | None = None,
    max_settled: int | None = None,
) -> list[int] | None:
    """source→target 최소 비용 경로(엣지 인덱스 열). 없으면 None.

    - forbidden: 진입 금지 노드 마스크(bytearray)
    - edge_factor: 특정 엣지 비용 배율 (페널티 KSP·GA 변이용)
    - jitter: (lo, hi) 균등 배율로 엣지 비용을 교란
    """
    n = len(adj.out)
    if source == target:
        return []
    dist = [float("inf")] * n
    pred: list[int] = [-1] * n
    dist[source] = 0.0
    heap = [(0.0, source)]
    rng = rng or random
    cost = adj.cost
    out = adj.out
    settled = 0
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        if u == target:
            break
        settled += 1
        if max_settled is not None and settled > max_settled:
            return None
        for e, v in out[u]:
            if forbidden is not None and forbidden[v] and v != target:
                continue
            w = cost[e]
            if edge_factor:
                w *= edge_factor.get(e, 1.0)
            if jitter is not None:
                w *= rng.uniform(jitter[0], jitter[1])
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                pred[v] = e
                heapq.heappush(heap, (nd, v))
    if dist[target] == float("inf"):
        return None
    path: list[int] = []
    v = target
    while v != source:
        e = pred[v]
        path.append(e)
        v = adj.src[e]
    path.reverse()
    return path


def penalty_k_shortest(adj: Adjacency, source: int, target: int, k: int, penalty: float = 1.6,
                       rng: random.Random | None = None) -> list[list[int]]:
    """사용한 엣지 비용을 누적 배율로 올리며 재탐색하는 간단한 K-대안 경로."""
    paths: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    factor: dict[int, float] = {}
    for _ in range(k * 3):
        path = shortest_path(adj, source, target, edge_factor=factor, rng=rng)
        if path is None:
            break
        key = tuple(path)
        if key not in seen:
            seen.add(key)
            paths.append(path)
            if len(paths) >= k:
                break
        for e in path:
            factor[e] = factor.get(e, 1.0) * penalty
    return paths
