"""지도 타일·그늘 프록시: 엔진 응답을 그대로 전달하고, 접근 로그에는 남기지 않는다."""


def test_tile_proxy_passes_bytes_and_cache_headers(client):
    r = client.get("/api/tiles/16/55000/25000.mvt")
    assert r.status_code == 200 and r.content == b"\x1a\x05tile"
    assert r.headers["content-type"].startswith("application/vnd.mapbox-vector-tile") and "max-age=3600" in r.headers["cache-control"]
    assert client.get("/api/tiles/12/1/1.mvt").status_code == 204
    assert client.get("/api/tiles/30/1/1.mvt").status_code == 404
    assert client.get("/api/tiles/meta").json()["minzoom"] == 14


def test_shade_proxy_forwards_params_and_errors(client):
    r = client.get("/api/shade", params={"min_lat": 35.15, "min_lng": 129.06, "max_lat": 35.16, "max_lng": 129.07, "at": "2026-08-03T13:00:00+09:00"})
    assert r.status_code == 200 and r.json()["ratios"] == {"1": 0.5, "2": 0.0} and r.json()["at"].startswith("2026-08-03T13:00:00")
    bad = client.get("/api/shade", params={"min_lat": 35.0, "min_lng": 129.0, "max_lat": 35.2, "max_lng": 129.2})
    assert bad.status_code == 422 and "확대" in bad.json()["detail"]
