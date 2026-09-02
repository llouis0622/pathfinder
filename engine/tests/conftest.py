import pytest

from app.graph.store import MemoryGraphStore
from app.pipeline.synthetic import build_grid_city


@pytest.fixture(scope="session")
def grid_city():
    graph, buildings = build_grid_city()
    return graph, buildings


@pytest.fixture(scope="session")
def store(grid_city):
    graph, buildings = grid_city
    return MemoryGraphStore(graph, buildings, source="grid_city")
