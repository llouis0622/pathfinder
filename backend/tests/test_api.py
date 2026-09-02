from datetime import datetime, timedelta, timezone

ROUTE_BODY = {
    "origin": {"lat": 35.15, "lng": 129.06, "name": "출발"},
    "destination": {"lat": 35.1536, "lng": 129.0726, "name": "도착"},
    "profile": "elderly",
    "departure_at": "2026-08-03T13:00:00+09:00",
}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["engine"]["status"] == "ok"


def test_profiles_from_engine_and_fallback(client, external):
    assert client.get("/api/profiles").json()[0]["id"] == "wheelchair"


def test_place_search_kakao_then_local(client, external):
    r = client.get("/api/place/search", params={"query": "부산역"})
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "kakao" and data["places"][0]["name"] == "부산역" and data["places"][0]["source"] == "kakao"
    external.kakao_status = 401
    r = client.get("/api/place/search", params={"query": "서면"})
    data = r.json()
    assert data["source"] == "local" and any(p["name"].startswith("서면") for p in data["places"])
    assert all(p["category"] == "지하철역" for p in data["places"][:2])


def test_place_search_local_only(client_no_kakao):
    data = client_no_kakao.get("/api/place/search", params={"query": "하단"}).json()
    assert data["source"] == "local" and data["places"][0]["name"] == "하단역"


def test_weather_current_and_forecast(client, external):
    r = client.get("/api/weather", params={"lat": 35.15, "lng": 129.06})
    w = r.json()
    assert w["source"] == "open_meteo" and w["feels_like_c"] == 34.2 and w["pm10"] == 40.0
    assert "heatwave" in w["flags"] and "heat" in w["flags"] and "rain" not in w["flags"]
    future = client.get("/api/weather", params={"lat": 35.15, "lng": 129.06, "at": "2036-01-01T09:20:00+09:00"}).json()
    assert future["forecast_for"].startswith("2036-01-01T09:00") and future["pm10"] == 95.0
    assert set(future["flags"]) >= {"cold", "windy", "bad_air"} and future["sky"] == "snow" and "rain" in future["flags"]


def test_manual_weather_wins_over_provider_none(external):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    cfg = Settings(database_url="sqlite+aiosqlite:///:memory:", engine_url="http://engine:8001", weather_provider="none")
    with TestClient(create_app(cfg)) as c:
        body = dict(ROUTE_BODY, weather_mode="manual", manual_weather={"rain": True})
        assert c.post("/api/route", json=body).json()["weather"]["flags"] == ["rain"]
        assert c.post("/api/route", json=ROUTE_BODY).json()["weather"]["source"] == "none"


def test_weather_failure_is_soft(client, external):
    external.open_meteo_fail = True
    w = client.get("/api/weather", params={"lat": 35.15, "lng": 129.06}).json()
    assert w["source"] == "unavailable" and w["flags"] == []


def test_route_search_stores_and_returns(client, external):
    r = client.post("/api/route", json=ROUTE_BODY)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["routes"]) == 3 and data["profile"] == "elderly"
    assert data["weather"]["source"] == "open_meteo" and "heatwave" in data["weather"]["flags"]
    assert data["metadata"]["backend_elapsed_ms"] >= 0
    sent = external.engine_calls[-1]
    assert sent["profile"] == "elderly" and sent["weather"]["feels_like_c"] == 34.2 and sent["options"]["k"] == 3
    assert sent["departure_at"].startswith("2026-08-03T13:00")
    stored = client.get(f"/api/route/{data['request_id']}")
    assert stored.status_code == 200
    s = stored.json()
    assert s["status"] == "ok" and len(s["routes"]) == 3 and s["origin"]["name"] == "출발"
    assert s["routes"][0]["rank"] == 1 and "badges" in s["routes"][0]


def test_route_manual_weather_and_none(client, external):
    body = dict(ROUTE_BODY, weather_mode="manual", manual_weather={"heatwave": True, "rain": True})
    r = client.post("/api/route", json=body)
    assert r.status_code == 200
    sent = external.engine_calls[-1]
    assert sent["weather"]["flags_explicit"] is True and sent["weather"]["heatwave"] and sent["weather"]["heat"] and sent["weather"]["rain"]
    assert r.json()["weather"]["source"] == "manual"
    body = dict(ROUTE_BODY, weather_mode="none")
    r = client.post("/api/route", json=body)
    assert r.json()["weather"]["source"] == "none"


def test_route_no_route_and_engine_down(client, external):
    external.engine_status = 422
    external.engine_detail = "휠체어 이용자 조건으로 통과 가능한 경로가 없습니다"
    r = client.post("/api/route", json=dict(ROUTE_BODY, profile="wheelchair"))
    assert r.status_code == 422 and "휠체어" in r.json()["detail"]
    external.engine_status = 500
    r = client.post("/api/route", json=ROUTE_BODY)
    assert r.status_code == 502


def test_route_validation(client):
    r = client.post("/api/route", json=dict(ROUTE_BODY, profile="general"))
    assert r.status_code == 422
    r = client.get("/api/route/not-a-uuid")
    assert r.status_code == 422
    r = client.get("/api/route/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_departure_in_past_uses_current(client, external):
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    w = client.get("/api/weather", params={"lat": 35.15, "lng": 129.06, "at": past}).json()
    assert w["forecast_for"] is None and w["observed_at"] == "2026-08-03T13:00"
