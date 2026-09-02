"""PostGIS 스토어 통합 테스트. PATHFINDER_TEST_DSN 에 접속되지 않으면 건너뛴다."""
import os

import numpy as np
import pytest

from app.graph.corridor import CorridorSpec
from app.graph.factory import build_store
from app.graph.store import SnapError
from app.pipeline.synthetic import _latlng, node_id
from app.routes.schemas import LatLng, SearchOptions, SearchRequest
from app.search.pipeline import search_routes

DSN = os.environ.get("PATHFINDER_TEST_DSN", "postgresql://pathfinder:pathfinder_dev@localhost:5432/pathfinder")


def _available() -> bool:
    try:
        import psycopg

        with psycopg.connect(DSN, connect_timeout=2) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _available(), reason="PostGIS 테스트 DB 없음")


@pytest.fixture(scope="module")
def pg_store(grid_city):
    from app.graph.postgis import PostgisGraphStore, connect, load_buildings, load_graph

    graph, buildings = grid_city
    with connect(DSN) as conn:
        result = load_graph(conn, graph, replace=True, meta={"fixture": "grid_city"})
        load_buildings(conn, buildings, replace=True, source="synthetic")
    assert result["nodes"] == graph.num_nodes and result["edges"] == graph.num_edges
    return PostgisGraphStore(DSN)


def test_describe_and_snap(pg_store, grid_city):
    graph, buildings = grid_city
    info = pg_store.describe()
    assert info["nodes"] == graph.num_nodes and info["edges"] == graph.num_edges and info["buildings"] == len(buildings)
    lat, lng = _latlng(3, 3)
    snapped = pg_store.nearest_walk_node(lat + 0.00005, lng)
    assert snapped.node_id == node_id(3, 3) and snapped.distance_m < 10
    with pytest.raises(SnapError):
        pg_store.nearest_walk_node(lat + 0.1, lng)


def test_corridor_matches_memory_store(pg_store, store):
    o, d = _latlng(8, 2), _latlng(8, 10)
    spec = CorridorSpec(o[0], o[1], d[0], d[1])
    pg = pg_store.corridor(spec)
    mem = store.corridor(spec)
    assert pg.num_nodes == mem.num_nodes
    assert set(pg.nodes["id"].tolist()) == set(mem.nodes["id"].tolist())
    assert pg.num_edges == mem.num_edges
    # 속성이 왕복 후에도 보존된다
    i = int(np.nonzero(pg.edges["stairs"] == 1)[0][0])
    j = pg.edges["id"][i]
    k = int(np.nonzero(mem.edges["id"] == j)[0][0])
    assert pg.edges["step_count"][i] == mem.edges["step_count"][k]
    assert pg.edges["ramp"][i] == mem.edges["ramp"][k]
    assert len(pg.edge_geometry(i)) >= 2


def test_buildings_in_bbox(pg_store, grid_city):
    _, buildings = grid_city
    bbox = (35.149, 129.059, 35.16, 129.075)
    found = pg_store.buildings_in(bbox)
    assert len(found) == len(buildings)
    assert any(b.height_m is None for b in found) and any(b.height_m == 60.0 for b in found)


def test_search_through_postgis_store(pg_store):
    o, d = _latlng(8, 0), _latlng(8, 23)
    req = SearchRequest(origin=LatLng(lat=o[0], lng=o[1]), destination=LatLng(lat=d[0], lng=d[1]), profile="wheelchair",
                        options=SearchOptions(seed=5))
    res = search_routes(pg_store, req)
    assert len(res.routes) == 3 and all(r.features.stairs_count == 0 for r in res.routes)


def test_factory_modes(pg_store):
    pg = build_store("postgis", dsn=DSN)
    assert pg.describe()["source"] == "postgis"
    mem = build_store("postgis_memory", dsn=DSN)
    assert mem.describe()["source"] == "postgis_memory" and mem.describe()["buildings"] > 0
    with pytest.raises(ValueError):
        build_store("nope")
