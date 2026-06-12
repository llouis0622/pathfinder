from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass
class Coordinate:
    lat: float
    lng: float


@dataclass
class PathResult:
    path: List[Coordinate]
    duration_min: float
    distance_m: float
    algorithm: str
    metadata: dict = field(default_factory=dict)


class BasePathfinder(ABC):
    def __init__(self, weights: dict):
        self.weights = weights

    @abstractmethod
    def find_path(self, origin: Coordinate, destination: Coordinate) -> PathResult:
        """경로 탐색 실행. 데이터 및 모델 학습 완료 후 구현."""
        pass

    def _apply_weights(self, edge_cost: float, edge_attrs: dict) -> float:
        """가중치 적용 로직. 모델 학습 완료 후 구현."""
        return edge_cost
