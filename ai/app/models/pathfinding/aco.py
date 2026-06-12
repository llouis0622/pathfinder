"""
Ant Colony Optimization (ACO) 기반 경로 탐색

개미 집단 최적화 알고리즘으로 페로몬 갱신을 통해 반복적으로 최적 경로를 수렴시킨다.

향후 구현 방향:
- 페로몬 초기값·증발율(ρ)·알파·베타를 가중치와 연동
- 각 개미는 weights 기반 휴리스틱 함수로 다음 노드 선택
- 반복 횟수, 개미 수는 하이퍼파라미터로 분리
- 교통약자 불가 경로 엣지는 페로몬 초기값 0으로 차단
"""

import math
from .base import BasePathfinder, Coordinate, PathResult


class ACOPathfinder(BasePathfinder):
    """Ant Colony Optimization 기반 경로 탐색기 (플레이스홀더)"""

    def find_path(self, origin: Coordinate, destination: Coordinate) -> PathResult:
        distance_m = self._straight_distance_m(origin, destination)
        duration_min = round(distance_m / 1000 / 4.0 * 60, 1)

        return PathResult(
            path=[origin, destination],
            duration_min=duration_min,
            distance_m=distance_m,
            algorithm="aco",
            metadata={
                "iterations": 0,
                "ants": 0,
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
