from app.models.pathfinding import ACOPathfinder, GAPathfinder, KSPPathfinder, TreePathfinder
from app.models.pathfinding.base import BasePathfinder, Coordinate, PathResult

# 알고리즘 이름 → 클래스 매핑
ALGORITHM_MAP: dict[str, type[BasePathfinder]] = {
    "ksp": KSPPathfinder,
    "ga": GAPathfinder,
    "aco": ACOPathfinder,
    "tree": TreePathfinder,
}


def run_pathfinding(
    origin: Coordinate,
    destination: Coordinate,
    algorithm: str,
    weights: dict,
) -> PathResult:
    """요청된 알고리즘 선택 후 경로 탐색 실행"""
    pathfinder_cls = ALGORITHM_MAP.get(algorithm, KSPPathfinder)
    pathfinder = pathfinder_cls(weights=weights)
    return pathfinder.find_path(origin, destination)
