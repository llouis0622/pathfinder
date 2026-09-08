"""개미 군집 최적화 (MMAS + ACS 의사난수 비례 규칙).

휴리스틱에 도착지 cost-to-go h(v)를 섞어 개미가 목적지 방향으로 가되,
페로몬·확률 선택으로 우회 경로도 탐험한다. 모든 완주 경로는 아카이브에 남긴다.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .common import Adjacency, path_key


@dataclass(frozen=True)
class ACOParams:
    ants: int = 24
    iterations: int = 60
    alpha: float = 1.0
    beta: float = 2.5
    rho: float = 0.12
    q0: float = 0.35
    lam: float = 0.6
    time_budget_s: float = 2.5
    stagnation_limit: int = 20
    max_steps_factor: float = 3.0
    min_steps: int = 40
    max_backtracks: int = 60
    seed: int | None = None


@dataclass
class ArchiveEntry:
    cost: float
    edges: list[int]
    origin: str


@dataclass
class ACOResult:
    best: ArchiveEntry | None
    archive: dict[tuple[int, ...], ArchiveEntry]
    iterations: int
    ants_completed: int
    ants_failed: int
    elapsed_s: float
    stopped_by: str
    history: list[float] = field(default_factory=list)


class AntColony:
    def __init__(
        self,
        adj: Adjacency,
        h: np.ndarray,
        source: int,
        target: int,
        route_cost: Callable[[list[int]], float],
        params: ACOParams | None = None,
    ) -> None:
        self.adj = adj
        self.source = source
        self.target = target
        self.route_cost = route_cost
        self.p = params or ACOParams()
        self.rng = random.Random(self.p.seed)
        self.h = h.tolist()
        n = len(adj.out)
        # 도달 가능한 이웃만 남긴 인접 리스트
        self.nbrs: list[list[tuple[int, int]]] = [[] for _ in range(n)]
        for u in range(n):
            self.nbrs[u] = [(e, v) for e, v in adj.out[u] if self.h[v] != float("inf")]
        E = len(adj.cost)
        lam = self.p.lam
        beta = self.p.beta
        self.etab: list[float] = [0.0] * E
        for u in range(n):
            for e, v in self.nbrs[u]:
                self.etab[e] = (1.0 / (adj.cost[e] + lam * self.h[v] + 1e-6)) ** beta
        self.tau: list[float] = []
        self.tau_min = self.tau_max = 0.0

    # ---------- 페로몬 ----------
    def _init_pheromone(self, seed_cost: float, n_edges: int) -> None:
        tau0 = 1.0 / (self.p.rho * max(seed_cost, 1.0))
        self.tau_max = tau0
        self.tau_min = tau0 / (2.0 * math.sqrt(max(n_edges, 1)))
        self.tau = [tau0] * len(self.adj.cost)

    def _deposit(self, entry: ArchiveEntry, weight: float = 1.0) -> None:
        delta = weight / max(entry.cost, 1.0)
        tmax = self.tau_max
        tau = self.tau
        for e in entry.edges:
            t = tau[e] + delta
            tau[e] = t if t < tmax else tmax

    def _evaporate(self) -> None:
        keep = 1.0 - self.p.rho
        tmin = self.tau_min
        self.tau = [t * keep if t * keep > tmin else tmin for t in self.tau]

    # ---------- 개미 ----------
    def _walk(self, max_steps: int) -> list[int] | None:
        rng = self.rng
        nbrs = self.nbrs
        tau = self.tau
        etab = self.etab
        alpha = self.p.alpha
        q0 = self.p.q0
        target = self.target
        visited = bytearray(len(nbrs))
        u = self.source
        visited[u] = 1
        path: list[int] = []
        backtracks = 0
        src = self.adj.src
        for _ in range(max_steps):
            cands = [(e, v) for e, v in nbrs[u] if not visited[v]]
            if not cands:
                # 막다른 곳: 한 칸 되돌아간다 (막힌 노드는 방문 표시가 남아 다시 들어가지 않는다)
                if not path or backtracks >= self.p.max_backtracks:
                    return None
                backtracks += 1
                u = src[path.pop()]
                continue
            if len(cands) == 1:
                e, v = cands[0]
            else:
                if alpha == 1.0:
                    weights = [tau[e] * etab[e] for e, _ in cands]
                else:
                    weights = [(tau[e] ** alpha) * etab[e] for e, _ in cands]
                if rng.random() < q0:
                    k = max(range(len(cands)), key=weights.__getitem__)
                else:
                    total = sum(weights)
                    r = rng.random() * total
                    acc = 0.0
                    k = len(cands) - 1
                    for i, w in enumerate(weights):
                        acc += w
                        if acc >= r:
                            k = i
                            break
                e, v = cands[k]
            path.append(e)
            visited[v] = 1
            u = v
            if u == target:
                return path
        return None

    # ---------- 실행 ----------
    def run(self, seeds: list[list[int]]) -> ACOResult:
        start = time.perf_counter()
        archive: dict[tuple[int, ...], ArchiveEntry] = {}
        best: ArchiveEntry | None = None
        for s in seeds:
            c = self.route_cost(s)
            if c == float("inf"):
                continue
            entry = ArchiveEntry(c, list(s), "seed")
            archive[path_key(s)] = entry
            if best is None or c < best.cost:
                best = entry
        if best is None:
            return ACOResult(None, archive, 0, 0, 0, time.perf_counter() - start, "no_seed")
        n_edges = sum(len(x) for x in self.nbrs)
        self._init_pheromone(best.cost, n_edges)
        for entry in archive.values():
            self._deposit(entry, weight=0.5)
        max_steps = max(self.p.min_steps, int(self.p.max_steps_factor * len(best.edges)))
        completed = failed = 0
        stagnation = 0
        history: list[float] = []
        stopped_by = "iterations"
        iterations = 0
        for it in range(self.p.iterations):
            iterations = it + 1
            iter_best: ArchiveEntry | None = None
            for _ in range(self.p.ants):
                path = self._walk(max_steps)
                if path is None:
                    failed += 1
                    continue
                key = path_key(path)
                entry = archive.get(key)
                if entry is None:
                    c = self.route_cost(path)
                    if c == float("inf"):
                        failed += 1
                        continue
                    entry = ArchiveEntry(c, path, "aco")
                    archive[key] = entry
                completed += 1   # 비용이 유한한 개미만 완주로 센다 (실패와 이중 계산하지 않는다)
                if iter_best is None or entry.cost < iter_best.cost:
                    iter_best = entry
            self._evaporate()
            if iter_best is not None:
                self._deposit(iter_best)
                if iter_best.cost < best.cost - 1e-9:
                    best = iter_best
                    stagnation = 0
                else:
                    stagnation += 1
            else:
                stagnation += 1
            self._deposit(best)
            history.append(best.cost)
            if stagnation >= self.p.stagnation_limit:
                stopped_by = "stagnation"
                break
            if time.perf_counter() - start > self.p.time_budget_s:
                stopped_by = "time_budget"
                break
        return ACOResult(best, archive, iterations, completed, failed, time.perf_counter() - start, stopped_by, history)
