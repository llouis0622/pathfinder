"""벡터 타일(edges·facilities·stops)과 화면 범위 그늘 API."""
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import mapbox_vector_tile
import numpy as np
from fastapi.testclient import TestClient

from app import tiles
from app.main import create_app

KST = ZoneInfo("Asia/Seoul")


def tile_at(lat: float, lng: float, z: int) -> tuple[int, int]:
    n = 1 << z
    x = int((lng + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def test_tile_bbox_roundtrip():
    x, y = tile_at(35.15, 129.06, 16)
    min_lat, min_lng, max_lat, max_lng = tiles.tile_bbox(16, x, y)
    assert min_lat < 35.15 < max_lat and min_lng < 129.06 < max_lng
    assert 0.004 < max_lat - min_lat < 0.006
    assert tiles.valid_tile(16, x, y) and not tiles.valid_tile(16, 1 << 16, 0)


def test_memory_tile_has_edges_facilities_and_stops(store):
    g = store.graph
    lat, lng = float(np.mean(g.nodes["lat"])), float(np.mean(g.nodes["lng"]))
    x, y = tile_at(lat, lng, 15)
    data = tiles.render_tile(store, 15, x, y)
    assert data
    decoded = mapbox_vector_tile.decode(data)
    assert set(decoded) >= {"edges", "facilities", "stops"}
    edges = decoded["edges"]["features"]
    assert edges and all(f["geometry"]["type"] == "LineString" for f in edges)
    props = edges[0]["properties"]
    assert props["kind"] in tiles.SHOWN_EDGE_KINDS and "stairs" in props and "id" not in props and edges[0]["id"] > 0
    assert any("length" in f["properties"] for f in edges)
    assert any("grade" in f["properties"] or "max_grade" in f["properties"] for f in edges)
    fac_types = {f["properties"]["type"] for f in decoded["facilities"]["features"]}
    assert fac_types & {"stairs", "elevator", "crossing", "kerb", "escalator", "vertical"}
    assert all(f["geometry"]["type"] == "Point" for f in decoded["facilities"]["features"])
    stops = decoded["stops"]["features"]
    assert stops and {f["properties"]["kind"] for f in stops} <= set(tiles.STOP_NODE_KINDS)
    # 같은 타일을 두 번 만들면 색인이 재사용된다
    assert tiles.render_tile(store, 15, x, y) == data
    # 줌이 낮거나 그래프 밖이면 비어 있다
    assert tiles.render_tile(store, 13, *tile_at(lat, lng, 13)) == b""
    assert tiles.render_tile(store, 16, *tile_at(37.5, 127.0, 16)) == b""


def test_shade_for_bbox(store):
    g = store.graph
    lat, lng = float(np.mean(g.nodes["lat"])), float(np.mean(g.nodes["lng"]))
    bbox = (lat - 0.004, lng - 0.005, lat + 0.004, lng + 0.005)
    noon = datetime(2026, 8, 3, 13, 0, tzinfo=KST)
    res = tiles.shade_for_bbox(store, bbox, noon)
    assert res["status"] == "computed" and res["edges"] > 0 and res["ratios"]
    assert all(0.0 <= v <= 1.0 for v in res["ratios"].values())
    assert any(v > 0 for v in res["ratios"].values())
    night = tiles.shade_for_bbox(store, bbox, datetime(2026, 8, 3, 23, 0, tzinfo=KST))
    assert night["status"] == "not_daylight" and all(v == 0 for v in night["ratios"].values())
    try:
        tiles.shade_for_bbox(store, (lat - 0.05, lng - 0.05, lat + 0.05, lng + 0.05), noon)
    except tiles.ShadeBboxError:
        pass
    else:
        raise AssertionError("넓은 bbox 는 거부돼야 한다")


def test_tile_and_shade_endpoints(store):
    g = store.graph
    lat, lng = float(np.mean(g.nodes["lat"])), float(np.mean(g.nodes["lng"]))
    x, y = tile_at(lat, lng, 16)
    with TestClient(create_app(store=store)) as c:
        meta = c.get("/api/tiles/meta").json()
        assert meta["minzoom"] == tiles.MIN_ZOOM and "edges" in meta["layers"]
        r = c.get(f"/api/tiles/16/{x}/{y}.mvt")
        assert r.status_code == 200 and r.headers["content-type"] == tiles.MVT_MEDIA_TYPE and "max-age" in r.headers["cache-control"]
        assert "edges" in mapbox_vector_tile.decode(r.content)
        assert c.get("/api/tiles/12/0/0.mvt").status_code == 204
        assert c.get("/api/tiles/16/99999999/0.mvt").status_code == 404
        s = c.get("/api/shade", params={"min_lat": lat - 0.004, "min_lng": lng - 0.005, "max_lat": lat + 0.004, "max_lng": lng + 0.005,
                                        "at": "2026-08-03T13:00:00+09:00"}).json()
        assert s["status"] == "computed" and s["ratios"]
        bad = c.get("/api/shade", params={"min_lat": lat - 0.1, "min_lng": lng - 0.1, "max_lat": lat + 0.1, "max_lng": lng + 0.1})
        assert bad.status_code == 422
