"""그래프 병합·연결·압축 유틸리티 (파이프라인용)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.spatial import cKDTree

from .geo import haversine_m, project_local
from .model import EDGE_FIELDS, NODE_FIELDS, Graph, tri

LINK_MAX_M = 200.0
COMPACT_MAX_LENGTH_M = 300.0
# 압축 시 두 엣지가 같아야 하는 속성
_COMPACT_KEYS = ("kind", "mode", "stairs", "ramp", "surface", "width_m", "tactile", "handrail", "crossing", "kerb", "lit", "indoor")


def _coerce(value, dtype: str):
    if dtype == "int8":
        return tri(value)
    if dtype.startswith("U"):
        return "" if value is None else str(value)
    if value is None:
        return np.nan if dtype.startswith("float") else 0
    return value


def _edge_arrays(records: list[dict]) -> dict[str, np.ndarray]:
    return {name: np.array([_coerce(r.get(name, default), dtype) for r in records], dtype=dtype) for name, dtype, default in EDGE_FIELDS}


def _geometry_arrays(geoms: list[list[tuple[float, float]]]) -> tuple[np.ndarray, np.ndarray]:
    counts = np.array([len(g) for g in geoms], dtype=np.int64)
    offsets = np.concatenate([[0], np.cumsum(counts)]).astype(np.int64)
    coords = np.asarray([p for g in geoms for p in g], dtype=np.float64).reshape(-1, 2)
    return offsets, coords


def all_geometries(graph: Graph) -> list[list[tuple[float, float]]]:
    return [graph.edge_geometry(i) for i in range(graph.num_edges)]


def merge_graphs(graphs: list[Graph]) -> Graph:
    """노드 id는 고유해야 한다. 엣지 id는 1부터 다시 매긴다."""
    graphs = [g for g in graphs if g is not None and g.num_nodes > 0]
    if not graphs:
        return Graph.empty()
    nodes = {k: np.concatenate([g.nodes[k] for g in graphs]) for k, _, _ in NODE_FIELDS}
    edges = {k: np.concatenate([g.edges[k] for g in graphs]) for k, _, _ in EDGE_FIELDS}
    edges["id"] = np.arange(1, len(edges["id"]) + 1, dtype=np.int64)
    geoms: list[list[tuple[float, float]]] = []
    for g in graphs:
        geoms.extend(all_geometries(g))
    offsets, coords = _geometry_arrays(geoms)
    return Graph(nodes, edges, offsets, coords)


@dataclass
class LinkReport:
    linked: int
    unlinked: list[int] = field(default_factory=list)


def link_transit_nodes(graph: Graph, max_distance_m: float = LINK_MAX_M, kinds: tuple[str, ...] = ("entrance", "stop")) -> tuple[Graph, LinkReport]:
    """출입구·정류장 노드를 가장 가까운 보행 노드와 link 엣지(양방향)로 잇는다."""
    walk_idx = np.nonzero(graph.nodes["kind"] == "walk")[0]
    target_idx = np.nonzero(np.isin(graph.nodes["kind"], kinds))[0]
    if len(walk_idx) == 0 or len(target_idx) == 0:
        return graph, LinkReport(0, [])
    lat, lng, ids = graph.nodes["lat"], graph.nodes["lng"], graph.nodes["id"]
    ref_lat, ref_lng = float(lat[walk_idx].mean()), float(lng[walk_idx].mean())
    wx, wy = project_local(lat[walk_idx], lng[walk_idx], ref_lat, ref_lng)
    tree = cKDTree(np.column_stack([wx, wy]))
    tx, ty = project_local(lat[target_idx], lng[target_idx], ref_lat, ref_lng)
    dist, pos = tree.query(np.column_stack([tx, ty]))
    is_link = graph.edges["kind"] == "link"
    has_link = set(graph.src[is_link].tolist()) | set(graph.dst[is_link].tolist())
    records: list[dict] = []
    geoms: list[list[tuple[float, float]]] = []
    unlinked: list[int] = []
    next_id = int(graph.edges["id"].max()) + 1 if graph.num_edges else 1
    for t, d, p in zip(target_idx, dist, pos):
        if int(t) in has_link:
            continue
        if d > max_distance_m:
            unlinked.append(int(ids[t]))
            continue
        w = int(walk_idx[p])
        L = max(float(haversine_m(lat[t], lng[t], lat[w], lng[w])), 1.0)
        for a, b in ((int(t), w), (w, int(t))):
            records.append({"id": next_id, "source": int(ids[a]), "target": int(ids[b]), "kind": "link", "mode": "walk",
                            "length_m": L, "grade_pct": 0.0, "indoor": False})
            geoms.append([(float(lat[a]), float(lng[a])), (float(lat[b]), float(lng[b]))])
            next_id += 1
    if not records:
        return graph, LinkReport(0, unlinked)
    add = _edge_arrays(records)
    edges = {k: np.concatenate([graph.edges[k], add[k]]) for k in graph.edges}
    offsets, coords = _geometry_arrays(all_geometries(graph) + geoms)
    return Graph(graph.nodes, edges, offsets, coords), LinkReport(len(records) // 2, unlinked)


def compact_walk_chains(graph: Graph, max_length_m: float = COMPACT_MAX_LENGTH_M) -> tuple[Graph, int]:
    """차수 2인 보행 노드(양방향 엣지 한 쌍씩)를 지나는 동일 속성 엣지를 합친다.

    반환: (압축 그래프, 제거된 노드 수). 도형은 이어 붙이고 경사는 이후 enrich_elevation 이 다시 계산한다.
    """
    e = graph.edges
    n_nodes = graph.num_nodes
    kind = e["kind"]
    is_walk_edge = kind == "walk"
    is_walk_node = graph.nodes["kind"] == "walk"

    # live 엣지: idx -> {src, dst, geom, length, attrs(원본 엣지 인덱스)}
    live: dict[int, dict] = {}
    adj: list[set[int]] = [set() for _ in range(n_nodes)]
    blocked_node = np.zeros(n_nodes, dtype=bool)   # 보행 이외 엣지가 닿은 노드
    for i in range(graph.num_edges):
        u, v = int(graph.src[i]), int(graph.dst[i])
        if not is_walk_edge[i]:
            blocked_node[u] = True
            blocked_node[v] = True
            continue
        live[i] = {"src": u, "dst": v, "geom": None, "length": float(e["length_m"][i]), "attrs": i}
        adj[u].add(i)
        adj[v].add(i)

    def geom_of(i: int) -> list[tuple[float, float]]:
        rec = live[i]
        if rec["geom"] is None:
            rec["geom"] = graph.edge_geometry(i)
        return rec["geom"]

    def attrs_equal(a: int, b: int) -> bool:
        for k in _COMPACT_KEYS:
            va, vb = e[k][a], e[k][b]
            if isinstance(va, np.floating):
                if not ((np.isnan(va) and np.isnan(vb)) or va == vb):
                    return False
            elif va != vb:
                return False
        return True

    next_idx = graph.num_edges
    removed_nodes = np.zeros(n_nodes, dtype=bool)
    removed = 0
    for v in range(n_nodes):
        if not is_walk_node[v] or blocked_node[v] or len(adj[v]) != 4:
            continue
        outs = {live[i]["dst"]: i for i in adj[v] if live[i]["src"] == v}
        ins = {live[i]["src"]: i for i in adj[v] if live[i]["dst"] == v}
        if len(outs) != 2 or len(ins) != 2 or set(outs) != set(ins) or v in outs:
            continue
        u, w = sorted(outs)
        e_uv, e_wv, e_vu, e_vw = ins[u], ins[w], outs[u], outs[w]
        if not (attrs_equal(live[e_uv]["attrs"], live[e_vw]["attrs"]) and attrs_equal(live[e_wv]["attrs"], live[e_vu]["attrs"])):
            continue
        L = live[e_uv]["length"] + live[e_vw]["length"]
        if L > max_length_m:
            continue
        for first, second, a, b in ((e_uv, e_vw, u, w), (e_wv, e_vu, w, u)):
            merged = {"src": a, "dst": b, "geom": list(geom_of(first)) + list(geom_of(second))[1:],
                      "length": live[first]["length"] + live[second]["length"], "attrs": live[first]["attrs"]}
            for old in (first, second):
                adj[live[old]["src"]].discard(old)
                adj[live[old]["dst"]].discard(old)
                del live[old]
            live[next_idx] = merged
            adj[a].add(next_idx)
            adj[b].add(next_idx)
            next_idx += 1
        removed_nodes[v] = True
        removed += 1

    # 결과 조립: 비보행 엣지(원본 그대로) + live 보행 엣지
    keep_orig = [i for i in range(graph.num_edges) if not is_walk_edge[i]]
    live_items = sorted(live.items())
    order = keep_orig + [i for i, _ in live_items]
    attrs_idx = keep_orig + [rec["attrs"] for _, rec in live_items]
    edges = {k: v[attrs_idx].copy() for k, v in e.items()}
    ids = graph.nodes["id"]
    geoms: list[list[tuple[float, float]]] = [graph.edge_geometry(i) for i in keep_orig]
    n_orig = len(keep_orig)
    for pos, (i, rec) in enumerate(live_items, start=n_orig):
        edges["source"][pos] = ids[rec["src"]]
        edges["target"][pos] = ids[rec["dst"]]
        edges["length_m"][pos] = rec["length"]
        geoms.append(geom_of(i) if i < graph.num_edges else rec["geom"])
    edges["id"] = np.arange(1, len(order) + 1, dtype=np.int64)
    offsets, coords = _geometry_arrays(geoms)
    nodes = {k: v[~removed_nodes] for k, v in graph.nodes.items()}
    return Graph(nodes, edges, offsets, coords), removed


def largest_component(graph: Graph) -> tuple[Graph, int]:
    """가장 큰 약연결 성분만 남긴다. 반환: (그래프, 제거 노드 수)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    n = graph.num_nodes
    if n == 0 or graph.num_edges == 0:
        return graph, 0
    m = coo_matrix((np.ones(graph.num_edges), (graph.src, graph.dst)), shape=(n, n))
    _, labels = connected_components(m, directed=True, connection="weak")
    biggest = np.bincount(labels).argmax()
    mask = labels == biggest
    return graph.subgraph(mask), int(n - mask.sum())
