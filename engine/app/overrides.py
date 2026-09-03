"""시설 제보로 만들어진 엣지 오버라이드를 회랑 그래프에 적용한다.

kind
- elevator_broken : 수직 이동 엣지의 엘리베이터를 '없음'으로 (휠체어·보행보조는 차단, 나머지는 계단 비용)
- stairs          : 엣지에 계단이 있다고 표시 (경사로 없음)
- kerb            : 턱(raised) 표시
- blocked         : 모든 프로필에서 통행 불가 (공사·폐쇄)
- ok              : 반대로 해당 엣지의 계단·턱 표시를 지우고 엘리베이터를 '있음'으로 (데이터 오류 정정)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

from .graph.model import TRI_FALSE, TRI_TRUE, Graph

KINDS = ("elevator_broken", "stairs", "kerb", "blocked", "ok")


@dataclass
class OverrideResult:
    applied: int = 0
    blocked: list[int] = field(default_factory=list)    # 회랑 내 엣지 인덱스
    missing: int = 0


def apply_overrides(graph: Graph, overrides: Iterable[dict]) -> OverrideResult:
    """회랑 그래프(요청마다 새로 만든 배열)에 속성 오버라이드를 반영한다. blocked 는 인덱스만 모아 돌려준다."""
    res = OverrideResult()
    items = list(overrides)
    if not items:
        return res
    ids = graph.edges["id"]
    index = {int(v): i for i, v in enumerate(ids.tolist())}
    for o in items:
        eid = int(o.get("edge_id", -1)) if isinstance(o, dict) else int(getattr(o, "edge_id", -1))
        kind = str(o.get("kind", "") if isinstance(o, dict) else getattr(o, "kind", ""))
        i = index.get(eid)
        if i is None:
            res.missing += 1
            continue
        if kind == "elevator_broken":
            graph.edges["elevator"][i] = TRI_FALSE
            graph.edges["escalator"][i] = TRI_FALSE
        elif kind == "stairs":
            graph.edges["stairs"][i] = TRI_TRUE
            graph.edges["ramp"][i] = TRI_FALSE
        elif kind == "kerb":
            graph.edges["kerb"][i] = "raised"
        elif kind == "blocked":
            res.blocked.append(i)
        elif kind == "ok":
            graph.edges["stairs"][i] = TRI_FALSE
            graph.edges["kerb"][i] = ""
            if graph.edges["kind"][i] == "vertical":
                graph.edges["elevator"][i] = TRI_TRUE
        else:
            res.missing += 1
            continue
        res.applied += 1
    return res


def block_costs(cost: np.ndarray, blocked_flags: np.ndarray, indices: list[int], reason: int = 9) -> None:
    for i in indices:
        cost[i] = np.inf
        blocked_flags[i] = reason
