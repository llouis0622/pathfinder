"""
Tree-based Search (A* / Decision Tree 하이브리드) 기반 경로 탐색

A* 휴리스틱 탐색과 의사결정 트리를 결합하여 교통약자 조건을 빠르게 필터링한다.

향후 구현 방향:
- 휴리스틱: Haversine 직선 거리 + weights 기반 패널티
- 의사결정 트리: 노드 진입 가능 여부(계단·경사·엘리베이터) 사전 분류
- 분류 모델은 수집된 실측 데이터로 학습 후 교체
- 오픈 셋(open set) 우선순위 큐에 heapq 사용
"""

import math
from .base import BasePathfinder, Coordinate, PathResult


class TreePathfinder(BasePathfinder):
    """Tree-based Search 기반 경로 탐색기 (플레이스홀더)"""

    def find_path(self, origin: Coordinate, destination: Coordinate) -> PathResult:
        distance_m = self._straight_distance_m(origin, destination)
        duration_min = round(distance_m / 1000 / 4.0 * 60, 1)

        return PathResult(
            path=[origin, destination],
            duration_min=duration_min,
            distance_m=distance_m,
            algorithm="tree",
            metadata={
                "nodes_explored": 0,
                "tree_depth": 0,
                "computation_time_ms": 0,
                "note": "placeholder — model not trained yet",
            },
        )

    def _straight_distance_m(self, a: Coordinate, b: Coordinate) -> float:
        R = 6_371_000
        dlat = math.radians(b.lat - a.lat)
        dlng = math.radians(b.lng - a.lng)
        h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a.lat)) * math.cos(math.radians(b.lat)) * math.sin(dlng / 2) ** 2
        return R * 2 * math.asin(math.sqrt(h))
