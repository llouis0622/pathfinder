"""시설 제보 오버라이드, 가장 가까운 엣지, 그래프 품질 통계, 타일 캐시."""
import numpy as np
from fastapi.testclient import TestClient

from app import tiles
from app.graph.model import TRI_FALSE, TRI_TRUE
from app.main import create_app
from app.overrides import apply_overrides
from app.routes.schemas import SearchRequest
from app.search.pipeline import NoRouteError, search_routes
from app.stats import graph_stats


def _center(store):
    g = store.graph
    return float(np.mean(g.nodes["lat"])), float(np.mean(g.nodes["lng"]))


def test_apply_overrides_mutates_only_known_edges(store):
    sub = store.graph.subgraph(np.ones(store.graph.num_nodes, dtype=bool))
    eid = int(sub.edges["id"][0])
    res = apply_overrides(sub, [{"edge_id": eid, "kind": "stairs"}, {"edge_id": eid, "kind": "kerb"}, {"edge_id": -5, "kind": "blocked"},
                               {"edge_id": eid, "kind": "weird"}])
    assert res.applied == 2 and res.missing == 2 and res.blocked == []
    assert sub.edges["stairs"][0] == TRI_TRUE and sub.edges["ramp"][0] == TRI_FALSE and sub.edges["kerb"][0] == "raised"
    assert store.graph.edges["stairs"][0] != TRI_TRUE or store.graph.edges["kerb"][0] != "raised"   # 원본은 그대로


def test_blocked_override_changes_or_removes_route(store):
    lat, lng = _center(store)
    base = SearchRequest(origin={"lat": lat - 0.004, "lng": lng - 0.006}, destination={"lat": lat + 0.004, "lng": lng + 0.006},
                         profile="elderly", options={"seed": 1, "time_budget_s": 1.0})
    res = search_routes(store, base)
    first = res.routes[0]
    # 1순위 경로의 첫 도보 엣지를 찾아 차단
    g = store.graph
    p0 = first.path[0]
    hit = tiles.nearest_edge(store, p0[0], p0[1], 80.0)
    assert hit is not None and hit["edge_id"] in set(g.edges["id"].tolist())
    blocked = base.model_copy(update={"overrides": [{"edge_id": hit["edge_id"], "kind": "blocked"}]})
    try:
        res2 = search_routes(store, blocked)
    except NoRouteError:
        return
    assert res2.metadata.overrides_applied == 1 and res2.metadata.blocked_edges >= res.metadata.blocked_edges + 1


def test_graph_stats_shape(store):
    st = graph_stats(store.graph, store.buildings)
    assert st["nodes"]["total"] == store.graph.num_nodes and st["edges"]["total"] == store.graph.num_edges
    assert 0 <= (st["walk"]["grade_coverage"] or 0) <= 1 and st["walk"]["edges"] > 0
    assert set(st["vertical"]["elevator"]) == {"yes", "no", "unknown"}
    assert st["buildings"]["total"] == len(store.buildings) and st["connectivity"]["components"] >= 1
    assert st["connectivity"]["largest_share"] is not None


def test_endpoints_nearest_edge_stats_and_tile_cache(store):
    lat, lng = _center(store)
    with TestClient(create_app(store=store)) as c:
        near = c.get("/api/nearest-edge", params={"lat": lat, "lng": lng, "max_distance_m": 200}).json()
        assert near["edge_id"] > 0 and near["kind"] in tiles.SHOWN_EDGE_KINDS and near["distance_m"] <= 200
        assert c.get("/api/nearest-edge", params={"lat": 37.5, "lng": 127.0}).status_code == 422
        st = c.get("/api/stats").json()
        assert st["nodes"]["total"] > 0 and st["source"] == "grid_city"
        assert c.get("/api/stats").json() == st   # 캐시
        n = 1 << 16
        import math
        x = int((lng + 180) / 360 * n)
        y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
        r1 = c.get(f"/api/tiles/16/{x}/{y}.mvt")
        r2 = c.get(f"/api/tiles/16/{x}/{y}.mvt")
        assert r1.headers["x-tile-cache"] == "miss" and r2.headers["x-tile-cache"] == "hit" and r1.content == r2.content
        stats = c.get("/api/tiles/cache").json()
        assert stats["hits"] >= 1 and stats["size"] >= 1
        m = c.get("/metrics").text
        assert "pathfinder_engine_tiles_total" in m
        r = c.get("/health", headers={"X-Request-ID": "abc-123"})
        assert r.headers["x-request-id"] == "abc-123"
