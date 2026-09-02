import numpy as np
import pytest

from app.graph.corridor import CorridorSpec, corridor_mask
from app.graph.model import TRI_FALSE, TRI_TRUE, TRI_UNKNOWN, Graph, tri
from app.graph.store import MemoryGraphStore, SnapError
from app.pipeline.synthetic import _latlng, node_id


def test_tri_state_parsing():
    assert tri(True) == TRI_TRUE
    assert tri(False) == TRI_FALSE
    assert tri(None) == TRI_UNKNOWN
    assert tri("yes") == TRI_TRUE
    assert tri("no") == TRI_FALSE
    assert tri("maybe") == TRI_UNKNOWN
    assert tri(float("nan")) == TRI_UNKNOWN


def test_from_records_builds_csr():
    g = Graph.from_records(
        [{"id": 1, "lat": 0, "lng": 0}, {"id": 2, "lat": 0, "lng": 0.001}, {"id": 3, "lat": 0.001, "lng": 0}],
        [{"id": 10, "source": 1, "target": 2, "length_m": 100}, {"id": 11, "source": 1, "target": 3, "length_m": 100},
         {"id": 12, "source": 2, "target": 3, "length_m": 100, "stairs": True, "elevator": None}],
    )
    assert g.num_nodes == 3 and g.num_edges == 3
    assert sorted(g.out_edge_indices(0).tolist()) == [0, 1]
    assert g.in_edge_indices(2).tolist() == [1, 2] or sorted(g.in_edge_indices(2).tolist()) == [1, 2]
    rec = g.edge_record(2)
    assert rec["stairs"] is True and rec["elevator"] is None and rec["surface"] == ""


def test_unknown_node_reference_raises():
    with pytest.raises(ValueError):
        Graph.from_records([{"id": 1}], [{"id": 1, "source": 1, "target": 99, "length_m": 1}])


def test_npz_roundtrip(tmp_path, grid_city):
    graph, _ = grid_city
    path = tmp_path / "g.npz"
    graph.save_npz(path)
    loaded = Graph.load_npz(path)
    assert loaded.num_nodes == graph.num_nodes and loaded.num_edges == graph.num_edges
    assert np.array_equal(loaded.edges["grade_pct"], graph.edges["grade_pct"], equal_nan=True)
    assert np.array_equal(loaded.edges["kind"], graph.edges["kind"])


def test_subgraph_keeps_only_internal_edges(grid_city):
    graph, _ = grid_city
    mask = graph.nodes["kind"] == "walk"
    sub = graph.subgraph(mask)
    assert sub.num_nodes == mask.sum()
    assert set(np.unique(sub.edges["kind"])) == {"walk"}


def test_corridor_mask_is_ellipse(grid_city):
    graph, _ = grid_city
    o = _latlng(8, 2)
    d = _latlng(8, 6)
    spec = CorridorSpec(o[0], o[1], d[0], d[1])
    mask = corridor_mask(graph, spec)
    idx_near = graph.id_to_index[node_id(8, 4)]
    idx_far = graph.id_to_index[node_id(0, 23)]
    assert mask[idx_near] and not mask[idx_far]
    # 대중교통 노드는 넓은 회랑을 쓴다
    transit = np.isin(graph.nodes["kind"], ["platform", "route_stop", "stop", "entrance"])
    assert mask[transit].sum() > 0


def test_snap_and_out_of_range(store):
    lat, lng = _latlng(3, 3)
    snapped = store.nearest_walk_node(lat + 0.00005, lng)
    assert snapped.node_id == node_id(3, 3)
    assert snapped.distance_m < 10
    with pytest.raises(SnapError):
        store.nearest_walk_node(lat + 0.1, lng)


def test_memory_store_requires_walk_nodes():
    g = Graph.from_records([{"id": 1, "kind": "stop"}], [])
    with pytest.raises(ValueError):
        MemoryGraphStore(g)
