"""유전 알고리즘: ACO 아카이브를 교차·변이로 다듬어 아카이브를 넓힌다."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable

from .aco import ArchiveEntry
from .common import Adjacency, edges_to_nodes, nodes_to_edges, path_key, remove_loops
from .dijkstra import shortest_path


@dataclass(frozen=True)
class GAParams:
    population: int = 30
    generations: int = 25
    crossover_rate: float = 0.7
    mutation_rate: float = 0.5
    tournament_k: int = 3
    elite: int = 2
    max_segment_ratio: float = 0.3
    jitter: tuple[float, float] = (0.6, 1.8)
    in_path_penalty: float = 3.0
    time_budget_s: float = 1.0
    seed: int | None = None


@dataclass
class GAResult:
    best: ArchiveEntry | None
    archive: dict[tuple[int, ...], ArchiveEntry]
    generations: int
    offspring_valid: int
    offspring_invalid: int
    elapsed_s: float


class GeneticRefiner:
    def __init__(self, adj: Adjacency, source: int, target: int,
                 route_cost: Callable[[list[int]], float], params: GAParams | None = None) -> None:
        self.adj = adj
        self.source = source
        self.target = target
        self.route_cost = route_cost
        self.p = params or GAParams()
        self.rng = random.Random(self.p.seed)

    # ---------- 연산자 ----------
    def crossover(self, a: list[int], b: list[int]) -> list[int] | None:
        """공통 중간 노드에서 두 부모를 잇는다. 결과는 노드 열."""
        inner_a = {n: i for i, n in enumerate(a[1:-1], start=1)}
        common = [n for n in b[1:-1] if n in inner_a]
        if not common:
            return None
        node = self.rng.choice(common)
        i = inner_a[node]
        j = b.index(node)
        child = a[:i] + b[j:]
        return remove_loops(child)

    def mutate(self, nodes: list[int]) -> list[int] | None:
        """부분 구간을 교란된 비용의 Dijkstra로 교체한다."""
        L = len(nodes)
        if L < 3:
            return None
        span = max(1, int(self.p.max_segment_ratio * L))
        i = self.rng.randrange(0, L - 1)
        j = min(L - 1, i + self.rng.randint(1, span))
        if j <= i:
            return None
        forbidden = bytearray(len(self.adj.out))
        for k, n in enumerate(nodes):
            if k < i or k > j:
                forbidden[n] = 1
        current = nodes_to_edges(nodes, self.adj)
        factor = {e: self.p.in_path_penalty for e in (current or [])}
        segment = shortest_path(self.adj, nodes[i], nodes[j], forbidden=forbidden, edge_factor=factor,
                                jitter=self.p.jitter, rng=self.rng, max_settled=20000)
        if segment is None:
            return None
        middle = edges_to_nodes(segment, self.adj, nodes[i])
        return remove_loops(nodes[:i] + middle + nodes[j + 1:])

    # ---------- 실행 ----------
    def _evaluate(self, node_path: list[int], archive: dict[tuple[int, ...], ArchiveEntry]) -> ArchiveEntry | None:
        if not node_path or node_path[0] != self.source or node_path[-1] != self.target:
            return None
        edges = nodes_to_edges(node_path, self.adj)
        if edges is None:
            return None
        key = path_key(edges)
        entry = archive.get(key)
        if entry is not None:
            return entry
        cost = self.route_cost(edges)
        if cost == float("inf"):
            return None
        entry = ArchiveEntry(cost, edges, "ga")
        archive[key] = entry
        return entry

    def _select(self, population: list[ArchiveEntry]) -> ArchiveEntry:
        k = min(self.p.tournament_k, len(population))
        return min(self.rng.sample(population, k), key=lambda e: e.cost)

    def run(self, archive: dict[tuple[int, ...], ArchiveEntry]) -> GAResult:
        start = time.perf_counter()
        pool = sorted(archive.values(), key=lambda e: e.cost)[: self.p.population]
        if not pool:
            return GAResult(None, archive, 0, 0, 0, 0.0)
        population = list(pool)
        valid = invalid = 0
        generations = 0
        for g in range(self.p.generations):
            generations = g + 1
            population.sort(key=lambda e: e.cost)
            next_gen: list[ArchiveEntry] = population[: self.p.elite]
            seen = {path_key(e.edges) for e in next_gen}
            attempts = 0
            while len(next_gen) < self.p.population and attempts < self.p.population * 4:
                attempts += 1
                parent = self._select(population)
                child_nodes = edges_to_nodes(parent.edges, self.adj, self.source)
                if self.rng.random() < self.p.crossover_rate and len(population) > 1:
                    other = self._select(population)
                    crossed = self.crossover(child_nodes, edges_to_nodes(other.edges, self.adj, self.source))
                    if crossed is not None:
                        child_nodes = crossed
                if self.rng.random() < self.p.mutation_rate:
                    mutated = self.mutate(child_nodes)
                    if mutated is not None:
                        child_nodes = mutated
                entry = self._evaluate(child_nodes, archive)
                if entry is None:
                    invalid += 1
                    continue
                valid += 1
                key = path_key(entry.edges)
                if key not in seen:
                    seen.add(key)
                    next_gen.append(entry)
            population = next_gen
            if time.perf_counter() - start > self.p.time_budget_s:
                break
        best = min(archive.values(), key=lambda e: e.cost) if archive else None
        return GAResult(best, archive, generations, valid, invalid, time.perf_counter() - start)
