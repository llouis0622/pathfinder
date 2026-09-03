import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.pipeline.synthetic import _latlng


@pytest.fixture(scope="module")
def client(store):
    app = create_app(store=store, config=Settings(graph_source="file", engine_time_budget_s=1.0))
    with TestClient(app) as c:
        yield c


def test_health_and_profiles(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["graph"]["nodes"] > 0
    p = client.get("/api/profiles").json()
    assert {x["id"] for x in p} == {"wheelchair", "elderly", "walking_aid", "visually_impaired"}
    assert all(x["description"] for x in p)


def test_snap(client):
    lat, lng = _latlng(3, 3)
    r = client.get("/api/snap", params={"lat": lat, "lng": lng})
    assert r.status_code == 200 and r.json()["distance_m"] < 1
    r = client.get("/api/snap", params={"lat": lat + 0.2, "lng": lng})
    assert r.status_code == 422


def test_search_endpoint(client):
    o, d = _latlng(8, 0), _latlng(8, 23)
    body = {"origin": {"lat": o[0], "lng": o[1]}, "destination": {"lat": d[0], "lng": d[1]}, "profile": "wheelchair",
            "departure_at": "2026-08-03T13:00:00+09:00", "weather": {"temp_c": 31, "feels_like_c": 34},
            "options": {"seed": 3}}
    r = client.post("/api/search", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["routes"]) == 3
    assert data["metadata"]["profile"] == "wheelchair" and "heatwave" in data["metadata"]["weather_flags"]
    assert data["metadata"]["shade_status"] == "computed"
    assert all(r_["features"]["stairs_count"] == 0 for r_ in data["routes"])
    assert data["routes"][0]["legs"][0]["kind"] == "walk"


def test_search_validation_and_no_route(client):
    o = _latlng(8, 0)
    body = {"origin": {"lat": o[0], "lng": o[1]}, "destination": {"lat": o[0], "lng": o[1]}, "profile": "elderly"}
    r = client.post("/api/search", json=body)
    assert r.status_code == 422
    bad = {"origin": {"lat": 0, "lng": 0}, "destination": {"lat": 1, "lng": 1}, "profile": "nope"}
    assert client.post("/api/search", json=bad).status_code == 422
    far = {"origin": {"lat": 0, "lng": 0}, "destination": {"lat": 1, "lng": 1}, "profile": "elderly"}
    r = client.post("/api/search", json=far)
    assert r.status_code == 422 and "보행 노드" in r.json()["detail"]
