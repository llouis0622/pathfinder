"""아카이브에서 서로 다른 상위 K개 경로를 고른다 (길이 가중 엣지 Jaccard)."""
from __future__ import annotations

from .aco import ArchiveEntry


def weighted_overlap(a: list[int], b: list[int], length: list[float]) -> float:
    sa, sb = set(a), set(b)
    inter = sum(length[e] for e in sa & sb)
    union = sum(length[e] for e in sa | sb)
    return inter / union if union > 0 else 1.0


def select_diverse(
    archive: dict[tuple[int, ...], ArchiveEntry],
    edge_length: list[float],
    k: int = 3,
    max_overlap: float = 0.6,
    max_cost_ratio: float = 1.6,
    ladder: tuple[tuple[float, float], ...] | None = None,
) -> list[ArchiveEntry]:
    """비용 순으로 훑되, (중복률 상한, 비용 배율 상한)을 단계적으로 완화한다.

    기본 사다리: (0.6, 1.6) → (0.8, 1.6) → (0.6, 2.2) → (0.8, 2.2) → (1.0, ∞)
    """
    ranked = sorted(archive.values(), key=lambda e: e.cost)
    if not ranked:
        return []
    best_cost = ranked[0].cost
    chosen: list[ArchiveEntry] = [ranked[0]]
    steps = ladder or (
        (max_overlap, max_cost_ratio),
        (min(max_overlap + 0.2, 1.0), max_cost_ratio),
        (max_overlap, max_cost_ratio + 0.6),
        (min(max_overlap + 0.2, 1.0), max_cost_ratio + 0.6),
        (1.0, float("inf")),
    )
    for overlap_limit, cost_limit in steps:
        for entry in ranked[1:]:
            if len(chosen) >= k:
                break
            if entry in chosen:
                continue
            if entry.cost > best_cost * cost_limit:
                break
            if all(weighted_overlap(entry.edges, c.edges, edge_length) <= overlap_limit for c in chosen):
                chosen.append(entry)
        if len(chosen) >= k:
            break
    return chosen[:k]
