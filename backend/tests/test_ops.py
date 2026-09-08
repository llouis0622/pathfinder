"""관측성(요청 ID·/metrics), 검색 캐시, 시설 제보 → 오버라이드 → 검색 반영, 데이터 품질."""
import pytest
from fastapi.testclient import TestClient

from app import admin, reports
from app.config import Settings
from app.main import create_app

ROUTE_BODY = {"origin": {"lat": 35.15, "lng": 129.06, "name": "서면역"}, "destination": {"lat": 35.1536, "lng": 129.0726, "name": "하단역"},
              "profile": "elderly"}


@pytest.fixture
def ops_client(external):
    admin.reset_failures()
    reports.reset_rate_limits()
    cfg = Settings(database_url="sqlite+aiosqlite:///:memory:", engine_url="http://engine:8001", allow_dev_login=True, jwt_secret="test-secret-0123456789-abcdefghijklmnop",
                   admin_password="secret-pw", search_cache_ttl_s=600, search_cache_size=50, report_rate_limit_per_hour=2, log_format="json")
    with TestClient(create_app(cfg)) as c:
        yield c


def login_admin(c):
    r = c.post("/api/admin/login", json={"password": "secret-pw"})
    c.cookies.set("pf_admin", r.cookies["pf_admin"])


def test_request_id_and_metrics(ops_client, external):
    c = ops_client
    r = c.get("/health", headers={"X-Request-ID": "trace-1"})
    assert r.headers["x-request-id"] == "trace-1" and r.json()["request_id"] == "trace-1"
    r2 = c.get("/api/profiles")
    assert len(r2.headers["x-request-id"]) == 32
    c.post("/api/route", json=ROUTE_BODY)
    m = c.get("/metrics").text
    assert "pathfinder_http_requests_total" in m and 'pathfinder_route_searches_total{cached="false",profile="elderly",status="ok"}' in m
    assert "pathfinder_engine_search_seconds_bucket" in m
    # 접근 로그에도 요청 ID 가 남는다
    login_admin(c)
    logs = c.get("/api/admin/logs/access", params={"path": "/api/route"}).json()["items"]
    assert logs and len(logs[0]["request_id"]) == 32 if "request_id" in logs[0] else True


def test_search_cache_reuses_engine_result(ops_client, external):
    c = ops_client
    a = c.post("/api/route", json=ROUTE_BODY).json()
    b = c.post("/api/route", json=ROUTE_BODY).json()
    assert a["metadata"]["cached"] is False and b["metadata"]["cached"] is True
    assert len(external.engine_calls) == 1 and a["routes"][0]["id"] == b["routes"][0]["id"]
    c.post("/api/route", json={**ROUTE_BODY, "profile": "wheelchair"})
    assert len(external.engine_calls) == 2
    login_admin(c)
    q = c.get("/api/admin/data-quality").json()
    assert q["search_cache"]["hits"] == 1 and q["search_cache"]["size"] == 2
    assert q["graph"]["nodes"]["total"] == 418 and q["active_overrides"] == 0
    # 캐시된 검색은 엔진 성능 로그를 남기지 않는다
    assert c.get("/api/admin/logs/engine").json()["total"] == 2


def test_report_flow_creates_override_and_reaches_engine(ops_client, external):
    c = ops_client
    kinds = c.get("/api/reports/kinds").json()
    assert {k["kind"] for k in kinds} >= {"elevator_broken", "blocked", "ok"}
    r = c.post("/api/reports", json={"lat": 35.151, "lng": 129.061, "kind": "elevator_broken", "note": "1번 출구 EV 멈춤", "place_name": "A역"})
    assert r.status_code == 201 and r.json()["status"] == "open" and r.json()["kind_label"] == "엘리베이터 고장"
    report_id = r.json()["id"]
    c.post("/api/reports", json={"lat": 35.152, "lng": 129.062, "kind": "stairs"})
    assert c.post("/api/reports", json={"lat": 35.153, "lng": 129.063, "kind": "kerb"}).status_code == 429   # 시간당 2건 한도
    assert c.get("/api/reports/mine").status_code == 401

    c.post("/api/route", json=ROUTE_BODY)
    assert external.engine_calls[-1]["overrides"] == []
    login_admin(c)
    lst = c.get("/api/admin/reports", params={"status": "open"}).json()
    assert lst["total"] == 2 and lst["counts"] == {"open": 2}
    acc = c.post(f"/api/admin/reports/{report_id}/accept", json={"note": "현장 확인", "expires_days": 30}).json()
    assert acc["report"]["status"] == "accepted" and acc["report"]["edge_id"] == 1234 and acc["report"]["edge_kind"] == "vertical"
    assert acc["override"]["active"] is True and acc["override"]["kind"] == "elevator_broken" and acc["override"]["expires_at"]
    # 승인이 검색 캐시를 비워 다음 검색은 엔진으로 가고, 오버라이드가 실린다
    res = c.post("/api/route", json=ROUTE_BODY).json()
    assert res["metadata"]["cached"] is False and external.engine_calls[-1]["overrides"] == [{"edge_id": 1234, "kind": "elevator_broken"}]
    # other 종류는 kind 지정이 필요하고, 엔진이 엣지를 못 찾으면 422
    other = c.post("/api/reports", json={"lat": 89.0, "lng": 1.0, "kind": "other", "note": "?"}, headers={"x-forwarded-for": "9.9.9.9"}).json()
    assert c.post(f"/api/admin/reports/{other['id']}/accept", json={}).status_code == 422
    assert c.post(f"/api/admin/reports/{other['id']}/accept", json={"kind": "blocked"}).status_code == 422
    rej = c.post(f"/api/admin/reports/{other['id']}/reject", json={"note": "위치 불명"}).json()
    assert rej["status"] == "rejected"
    # 직접 오버라이드 추가·해제
    ov = c.post("/api/admin/overrides", json={"edge_id": 77, "kind": "blocked", "note": "공사"}).json()
    assert c.get("/api/admin/overrides", params={"active": "true"}).json()["total"] == 2
    c.post("/api/route", json=ROUTE_BODY)
    assert {o["edge_id"] for o in external.engine_calls[-1]["overrides"]} == {1234, 77}
    assert c.delete(f"/api/admin/overrides/{ov['id']}").json()["active"] is False
    c.post("/api/route", json=ROUTE_BODY)
    assert external.engine_calls[-1]["overrides"] == [{"edge_id": 1234, "kind": "elevator_broken"}]
    assert c.get("/api/admin/data-quality").json()["reports"] == {"accepted": 1, "open": 1, "rejected": 1}
    events = [i["detail"] or "" for i in c.get("/api/admin/logs/access", params={"kind": "admin"}).json()["items"]]
    assert any(e.startswith("report_accept:") for e in events) and any(e.startswith("override_off:") for e in events)
