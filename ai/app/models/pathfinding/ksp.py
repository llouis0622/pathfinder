"""
K-Shortest Path (KSP) 알고리즘

Yen's K-Shortest Path 알고리즘을 기반으로 교통 그래프에서 K개의 최단 경로를 탐색한다.
가중치(weights)를 엣지 비용에 반영하여 교통약자 맞춤 경로를 선별한다.

향후 구현 방향:
- PostGIS 기반 도로 그래프 구축 (networkx + osmnx)
- 엣지 속성: 계단 여부, 경사도, 엘리베이터 유무, 보도 폭 등
- _apply_weights() 오버라이드로 프로필별 비용 재계산
"""

import math
from .base import BasePathfinder, Coordinate, PathResult


class KSPPathfinder(BasePathfinder):
    """K-Shortest Path 기반 경로 탐색기 (플레이스홀더)"""

    def find_path(self, origin: Coordinate, destination: Coordinate) -> PathResult:
        distance_m = self._straight_distance_m(origin, destination)
        duration_min = round(distance_m / 1000 / 4.0 * 60, 1)

        return PathResult(
            path=[origin, destination],
            duration_min=duration_min,
            distance_m=distance_m,
            algorithm="ksp",
            metadata={
                "nodes_explored": 0,
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
