import numpy as np

from app.graph.merge import compact_walk_chains, largest_component, link_transit_nodes, merge_graphs
from app.graph.model import Graph
from app.pipeline.synthetic import _latlng, node_id


def _chain(n: int, surface_change_at: int | None = None, spacing: float = 0.0005):
    nodes = [{"id": i, "kind": "walk", "lat": 35.1, "lng": 129.0 + i * spacing} for i in range(n)]
    edges = []
    eid = 1
    for i in range(n - 1):
        surface = "gravel" if (surface_change_at is not None and i >= surface_change_at) else "asphalt"
        for a, b in ((i, i + 1), (i + 1, i)):
            edges.append({"id": eid, "source": a, "target": b, "kind": "walk", "length_m": 45.0, "surface": surface})
            eid += 1
    return Graph.from_records(nodes, edges)


def test_compact_chain_merges_uniform_segments():
    g = _chain(6)
    c, removed = compact_walk_chains(g, max_length_m=300)
    assert removed == 4
    assert c.num_nodes == 2 and c.num_edges == 2
    assert set(c.edges["length_m"].tolist()) == {225.0}
    geom = c.edge_geometry(0)
    assert len(geom) == 6


def test_compact_respects_attribute_change_and_length_cap():
    g = _chain(6, surface_change_at=2)
    c, removed = compact_walk_chains(g, max_length_m=300)
    # 0-1-2 (asphalt) 와 2-3-4-5 (gravel): 노드 2 는 속성 경계라 남는다
    assert 2 in c.nodes["id"].tolist()
    assert removed == 3
    g2 = _chain(6)
    c2, removed2 = compact_walk_chains(g2, max_length_m=100)
    assert removed2 == 2 and c2.num_edges == 6   # 90 m 이하 짝만 합쳐진다 (0-1-2, 2-3-4 → 노드 1, 3 제거)


def test_compact_keeps_transit_touch_and_degree4(grid_city):
    graph, _ = grid_city
    c, removed = compact_walk_chains(graph)
    assert removed == 4      # 격자 내부는 차수 4, 네 모서리만 차수 2 → 모서리 4개가 합쳐진다
    assert c.num_edges == graph.num_edges - 8   # 모서리마다 엣지 4개 → 2개
    # 대중교통이 닿은 노드(출입구·정류장 링크)는 남아 있다
    assert (c.nodes["kind"] != "walk").sum() == (graph.nodes["kind"] != "walk").sum()
    assert (c.edges["kind"] == "link").sum() == (graph.edges["kind"] == "link").sum()


def test_merge_and_link(grid_city):
    graph, _ = grid_city
    walk = graph.subgraph(graph.nodes["kind"] == "walk")
    transit = graph.subgraph(graph.nodes["kind"] != "walk")
    merged = merge_graphs([walk, transit])
    assert merged.num_nodes == graph.num_nodes
    assert np.array_equal(np.sort(merged.edges["id"]), np.arange(1, merged.num_edges + 1))
    linked, report = link_transit_nodes(merged, max_distance_m=50)
    entrances = int((graph.nodes["kind"] == "entrance").sum()) + int((graph.nodes["kind"] == "stop").sum())
    assert report.linked == entrances and not report.unlinked
    assert (linked.edges["kind"] == "link").sum() == 2 * entrances
    # 이미 링크가 있으면 다시 만들지 않는다
    again, report2 = link_transit_nodes(linked, max_distance_m=50)
    assert report2.linked == 0 and again.num_edges == linked.num_edges


def test_link_reports_far_nodes():
    nodes = [{"id": 1, "kind": "walk", "lat": 35.1, "lng": 129.0}, {"id": 2, "kind": "entrance", "lat": 35.2, "lng": 129.0}]
    g = Graph.from_records(nodes, [])
    linked, report = link_transit_nodes(g, max_distance_m=100)
    assert report.linked == 0 and report.unlinked == [2] and linked.num_edges == 0


def test_largest_component():
    nodes = [{"id": i, "kind": "walk", "lat": 35.1, "lng": 129.0 + i * 0.001} for i in range(5)]
    edges = [{"id": 1, "source": 0, "target": 1, "length_m": 10}, {"id": 2, "source": 1, "target": 2, "length_m": 10},
             {"id": 3, "source": 3, "target": 4, "length_m": 10}]
    g, removed = largest_component(Graph.from_records(nodes, edges))
    assert removed == 2 and set(g.nodes["id"].tolist()) == {0, 1, 2}


def test_grid_ids_helper():
    assert node_id(3, 4) == 304 and _latlng(0, 0)[0] == 35.15
