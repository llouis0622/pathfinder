"""그래프 데이터 품질 통계 (관리자 데이터 품질 대시보드용). 한 번 계산해 캐시한다."""
from __future__ import annotations

import threading
from collections import Counter
from typing import Any

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from .graph.model import TRI_FALSE, TRI_TRUE, TRI_UNKNOWN, Graph
from .graph.store import Building, MemoryGraphStore


def _tri_counts(arr: np.ndarray) -> dict[str, int]:
    return {"yes": int(np.count_nonzero(arr == TRI_TRUE)), "no": int(np.count_nonzero(arr == TRI_FALSE)),
            "unknown": int(np.count_nonzero(arr == TRI_UNKNOWN))}


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def graph_stats(graph: Graph, buildings: list[Building]) -> dict[str, Any]:
    n, e = graph.nodes, graph.edges
    kinds = e["kind"]
    walk = (kinds == "walk") | (kinds == "link")
    vertical = kinds == "vertical"
    W = int(np.count_nonzero(walk))
    walk_len = float(np.nansum(e["length_m"][walk])) if W else 0.0
    grade_known = int(np.count_nonzero(walk & ~np.isnan(e["max_grade_pct"])))
    width_known = int(np.count_nonzero(walk & ~np.isnan(e["width_m"])))
    surface_known = int(np.count_nonzero(walk & (e["surface"] != "")))
    stairs = walk & (e["stairs"] == TRI_TRUE)
    stairs_no_ramp = stairs & (e["ramp"] != TRI_TRUE)
    kerbs = Counter(str(k) for k in e["kerb"][walk] if k)
    crossings = Counter(str(c) for c in e["crossing"][walk] if c)
    steep = walk & (np.nan_to_num(e["max_grade_pct"], nan=0.0) > 10)

    # 보행망 연결성 (walk 노드 + walk/link 엣지)
    walk_nodes = n["kind"] == "walk"
    N = graph.num_nodes
    comps = {"components": 0, "largest_share": None, "isolated_walk_nodes": 0}
    if N and W:
        m = coo_matrix((np.ones(W), (graph.src[walk], graph.dst[walk])), shape=(N, N))
        count, labels = connected_components(m, directed=False)
        sizes = Counter(labels[walk_nodes].tolist())
        deg = np.bincount(np.concatenate([graph.src[walk], graph.dst[walk]]), minlength=N)
        comps = {"components": int(len(sizes)), "largest_share": _ratio(max(sizes.values()) if sizes else 0, int(np.count_nonzero(walk_nodes))),
                 "isolated_walk_nodes": int(np.count_nonzero(walk_nodes & (deg == 0)))}

    heights = [b.height_m for b in buildings]
    known_h = sum(1 for h in heights if h is not None and h > 0)
    return {
        "nodes": {"total": int(N), "by_kind": dict(Counter(n["kind"].tolist()))},
        "edges": {"total": int(graph.num_edges), "by_kind": dict(Counter(kinds.tolist()))},
        "walk": {
            "edges": W, "length_km": round(walk_len / 1000, 1),
            "grade_coverage": _ratio(grade_known, W), "width_coverage": _ratio(width_known, W), "surface_coverage": _ratio(surface_known, W),
            "stairs": int(np.count_nonzero(stairs)), "stairs_without_ramp": int(np.count_nonzero(stairs_no_ramp)),
            "steep_over_10pct": int(np.count_nonzero(steep)), "kerbs": dict(kerbs), "crossings": dict(crossings),
            "tactile": _tri_counts(e["tactile"][walk]), "lit": _tri_counts(e["lit"][walk]),
        },
        "vertical": {"edges": int(np.count_nonzero(vertical)), "elevator": _tri_counts(e["elevator"][vertical]),
                     "escalator": _tri_counts(e["escalator"][vertical])},
        "transit": {"stops": int(np.count_nonzero(n["kind"] == "stop")), "platforms": int(np.count_nonzero(n["kind"] == "platform")),
                    "entrances": int(np.count_nonzero(n["kind"] == "entrance")), "routes": int(len(set(e["route_id"][kinds == "ride"].tolist()))),
                    "low_floor_known": int(np.count_nonzero(~np.isnan(e["low_floor_ratio"][kinds == "board"])))},
        "buildings": {"total": len(buildings), "height_known": known_h, "height_coverage": _ratio(known_h, len(buildings))},
        "connectivity": comps,
    }


_STATS_LOCK = threading.Lock()


def store_stats(store: Any) -> dict[str, Any]:
    cached = getattr(store, "_stats_cache", None)
    if cached is not None:
        return cached
    with _STATS_LOCK:
        cached = getattr(store, "_stats_cache", None)
        if cached is not None:
            return cached
        return _compute_store_stats(store)


def _compute_store_stats(store: Any) -> dict[str, Any]:
    if isinstance(store, MemoryGraphStore):
        result = graph_stats(store.graph, store.buildings)
    else:
        result = graph_stats(store.load_full(), store.load_all_buildings())
    result["source"] = store.describe().get("source")
    try:
        store._stats_cache = result  # type: ignore[attr-defined]
    except AttributeError:
        pass
    return result
