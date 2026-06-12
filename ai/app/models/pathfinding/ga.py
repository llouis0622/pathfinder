"""
Genetic Algorithm (GA) 기반 경로 탐색

유전 알고리즘을 사용하여 다중 목적(시간·거리·편의시설)을 동시에 최적화하는 경로를 탐색한다.

향후 구현 방향:
- 염색체: 경유 노드 시퀀스
- 적합도 함수: weights 기반 다중 목적 합산 비용
- 연산자: 교차(crossover), 변이(mutation), 선택(selection)
- 세대 수·인구 수는 하이퍼파라미터로 분리
"""

import math
from .base import BasePathfinder, Coordinate, PathResult


class GAPathfinder(BasePathfinder):
    """Genetic Algorithm 기반 경로 탐색기 (플레이스홀더)"""

    def find_path(self, origin: Coordinate, destination: Coordinate) -> PathResult:
        distance_m = self._straight_distance_m(origin, destination)
        duration_min = round(distance_m / 1000 / 4.0 * 60, 1)

        return PathResult(
            path=[origin, destination],
            duration_min=duration_min,
            distance_m=distance_m,
            algorithm="ga",
            metadata={
                "generations": 0,
                "population_size": 0,
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
