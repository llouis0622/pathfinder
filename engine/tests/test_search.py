import random

import numpy as np
import pytest

from app.cost.model import compute_costs, route_cost
from app.cost.profiles import get_profile
from app.graph.model import TRI_TRUE
from app.pipeline.synthetic import node_id
from app.search.aco import ACOParams, AntColony
from app.search.common import Adjacency, edges_to_nodes, nodes_to_edges, remove_loops
from app.search.dijkstra import cost_to_go, penalty_k_shortest, shortest_path
from app.search.diversity import select_diverse, weighted_overlap
from app.search.ga import GAParams, GeneticRefiner


def _setup(graph, profile_id):
    profile = get_profile(profile_id)
    cost = compute_costs(graph, profile)
    adj = Adjacency.build(graph, cost.cost)
    o = graph.id_to_index[node_id(8, 0)]
    d = graph.id_to_index[node_id(8, 23)]
    h = cost_to_go(graph, cost.cost, d)
    return profile, cost, adj, o, d, h


def _assert_valid(graph, adj, edges, o, d):
    nodes = edges_to_nodes(edges, adj, o)
    assert nodes[0] == o and nodes[-1] == d
    assert len(set(nodes)) == len(nodes), "단순 경로가 아님"
    for e, (u, v) in zip(edges, zip(nodes, nodes[1:])):
        assert adj.src[e] == u and adj.dst[e] == v


def test_remove_loops():
    assert remove_loops([1, 2, 3, 2, 4]) == [1, 2, 4]
    assert remove_loops([1, 2, 3, 4]) == [1, 2, 3, 4]
    assert remove_loops([1, 2, 3, 1, 5]) == [1, 5]


def test_cost_to_go_matches_forward_dijkstra(grid_city):
    graph, _ = grid_city
    _, cost, adj, o, d, h = _setup(graph, "elderly")
    path = shortest_path(adj, o, d)
    assert path is not None
    assert adj.path_cost(path) == np.testing.assert_allclose(adj.path_cost(path), h[o], rtol=1e-6) or True
    np.testing.assert_allclose(adj.path_cost(path), h[o], rtol=1e-6)


def test_shortest_path_respects_forbidden_and_factor(grid_city):
    graph, _ = grid_city
    _, cost, adj, o, d, h = _setup(graph, "elderly")
    base = shortest_path(adj, o, d)
    mid = edges_to_nodes(base, adj, o)[len(base) // 2]
    forbidden = bytearray(len(adj.out))
    forbidden[mid] = 1
    alt = shortest_path(adj, o, d, forbidden=forbidden)
    assert alt is not None and mid not in edges_to_nodes(alt, adj, o)
    ks = penalty_k_shortest(adj, o, d, k=3)
    assert len(ks) == 3 and len({tuple(p) for p in ks}) == 3


def test_wheelchair_paths_never_use_blocked_edges(grid_city):
    graph, _ = grid_city
    profile, cost, adj, o, d, h = _setup(graph, "wheelchair")
    assert cost.n_blocked > 0
    seeds = [shortest_path(adj, o, d)] + penalty_k_shortest(adj, o, d, 3)
    res = AntColony(adj, h, o, d, lambda e: route_cost(e, cost, graph), ACOParams(seed=7, iterations=30)).run(seeds)
    assert res.best is not None and len(res.archive) > len(seeds)
    stairs = graph.edges["stairs"] == TRI_TRUE
    ramp = graph.edges["ramp"] == TRI_TRUE
    for entry in res.archive.values():
        _assert_valid(graph, adj, entry.edges, o, d)
        for e in entry.edges:
            assert cost.blocked[e] == 0
            assert not stairs[e] or ramp[e]
    assert res.best.cost <= min(route_cost(s, cost, graph) for s in seeds) + 1e-6


def test_aco_completion_rate_is_reasonable(grid_city):
    graph, _ = grid_city
    profile, cost, adj, o, d, h = _setup(graph, "elderly")
    seeds = [shortest_path(adj, o, d)]
    res = AntColony(adj, h, o, d, lambda e: route_cost(e, cost, graph), ACOParams(seed=3, iterations=15, stagnation_limit=100)).run(seeds)
    assert res.iterations == 15
    assert res.ants_completed >= 0.6 * (res.ants_completed + res.ants_failed)


def test_ga_operators_produce_valid_paths(grid_city):
    graph, _ = grid_city
    profile, cost, adj, o, d, h = _setup(graph, "elderly")
    rc = lambda e: route_cost(e, cost, graph)  # noqa: E731
    seeds = [shortest_path(adj, o, d)] + penalty_k_shortest(adj, o, d, 4)
    ga = GeneticRefiner(adj, o, d, rc, GAParams(seed=11, generations=5, population=12))
    a = edges_to_nodes(seeds[0], adj, o)
    b = edges_to_nodes(seeds[1], adj, o)
    child = ga.crossover(a, b)
    if child is not None:
        assert child[0] == o and child[-1] == d and len(set(child)) == len(child)
        assert nodes_to_edges(child, adj) is not None
    rng = random.Random(1)
    mutated_any = False
    for _ in range(20):
        m = ga.mutate(list(a))
        if m is not None:
            mutated_any = True
            assert m[0] == o and m[-1] == d and len(set(m)) == len(m)
            assert nodes_to_edges(m, adj) is not None
    assert mutated_any
    archive = {tuple(s): type("E", (), {})() for s in []}
    from app.search.aco import ArchiveEntry
    archive = {tuple(s): ArchiveEntry(rc(s), s, "seed") for s in seeds}
    res = ga.run(archive)
    assert res.offspring_valid > 0
    assert len(res.archive) >= len(seeds)
    for entry in res.archive.values():
        _assert_valid(graph, adj, entry.edges, o, d)
    assert rng is not None


def test_select_diverse_prefers_low_overlap():
    from app.search.aco import ArchiveEntry
    length = [100.0] * 10
    a = ArchiveEntry(100, [0, 1, 2, 3], "seed")
    b = ArchiveEntry(105, [0, 1, 2, 3, 4], "aco")   # a와 80% 겹침
    c = ArchiveEntry(120, [5, 6, 7, 8], "aco")   # 완전히 다름
    archive = {tuple(x.edges): x for x in (a, b, c)}
    chosen = select_diverse(archive, length, k=2)
    assert [x.cost for x in chosen] == [100, 120]
    assert weighted_overlap(a.edges, b.edges, length) == pytest.approx(0.8)
    chosen3 = select_diverse(archive, length, k=3)
    assert len(chosen3) == 3
