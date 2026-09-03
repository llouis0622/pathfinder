"""관리자 API: 로그인·잠금, 접근 로그 미들웨어, 엔진 성능·정책 갱신 기록, 대시보드·로그·사용자·분석·내보내기."""
import pytest
from fastapi.testclient import TestClient

from app import admin
from app.config import Settings
from app.main import create_app

ROUTE_BODY = {
    "origin": {"lat": 35.15, "lng": 129.06, "name": "서면역"},
    "destination": {"lat": 35.1536, "lng": 129.0726, "name": "하단역"},
    "profile": "elderly",
}


@pytest.fixture
def admin_client(external):
    admin.reset_failures()
    cfg = Settings(database_url="sqlite+aiosqlite:///:memory:", engine_url="http://engine:8001", allow_dev_login=True,
                   personalization_epsilon=0.0, jwt_secret="test-secret", admin_password="secret-pw", admin_login_max_failures=3,
                   admin_login_lockout_s=60)
    with TestClient(create_app(cfg)) as c:
        yield c


def login_admin(c: TestClient) -> None:
    r = c.post("/api/admin/login", json={"password": "secret-pw"})
    assert r.status_code == 200 and "pf_admin" in r.cookies
    c.cookies.set("pf_admin", r.cookies["pf_admin"])


def seed(c: TestClient) -> tuple[str, str]:
    """데모 사용자로 검색 2회 + 3순위 선택 1회. (request_id, user_id) 반환."""
    r = c.post("/api/auth/dev/login", params={"nickname": "관리테스트"})
    user_id = r.json()["id"]
    c.cookies.set("pf_session", r.cookies["pf_session"])
    first = c.post("/api/route", json=ROUTE_BODY).json()
    chosen = first["routes"][-1]["id"]
    assert c.post(f"/api/route/{first['request_id']}/choose", json={"route_id": chosen}).json()["learned"] is True
    second = c.post("/api/route", json=ROUTE_BODY).json()
    assert second["personalized"] is True
    c.cookies.delete("pf_session")
    return first["request_id"], user_id


def test_admin_disabled_when_no_password(client):
    assert client.get("/api/admin/me").json() == {"configured": False, "admin": False}
    assert client.post("/api/admin/login", json={"password": "x"}).status_code == 404
    assert client.get("/api/admin/overview").status_code == 404


def test_admin_login_lockout_and_session(admin_client):
    c = admin_client
    assert c.get("/api/admin/me").json() == {"configured": True, "admin": False}
    assert c.get("/api/admin/overview").status_code == 401
    for _ in range(3):
        assert c.post("/api/admin/login", json={"password": "wrong"}).status_code == 401
    locked = c.post("/api/admin/login", json={"password": "secret-pw"})
    assert locked.status_code == 429
    admin.reset_failures()
    login_admin(c)
    assert c.get("/api/admin/me").json()["admin"] is True
    assert c.get("/api/admin/overview").status_code == 200
    # 관리자 로그인 이벤트가 접근 로그에 남는다
    logs = c.get("/api/admin/logs/access", params={"kind": "admin"}).json()
    details = [i["detail"] for i in logs["items"]]
    assert "login" in details and "login_failed" in details and "login_locked" in details
    c.post("/api/admin/logout")
    c.cookies.delete("pf_admin")
    assert c.get("/api/admin/overview").status_code == 401


def test_access_log_records_api_and_auth_events(admin_client):
    c = admin_client
    request_id, user_id = seed(c)
    login_admin(c)
    logs = c.get("/api/admin/logs/access", params={"size": 200}).json()
    assert logs["total"] >= 5
    by_path = {(i["method"], i["path"]): i for i in logs["items"]}
    route = by_path[("POST", "/api/route")]
    assert route["status"] == 200 and route["kind"] == "api" and route["user_id"] == user_id and route["duration_ms"] is not None
    dev = by_path[("POST", "/api/auth/dev/login")]
    assert dev["kind"] == "auth" and dev["detail"] == "login:dev" and dev["user"]["nickname"] == "관리테스트"
    only_auth = c.get("/api/admin/logs/access", params={"kind": "auth"}).json()
    assert all(i["kind"] == "auth" for i in only_auth["items"]) and only_auth["total"] >= 1
    errors = c.get("/api/admin/logs/access", params={"status_min": 400}).json()
    assert all(i["status"] >= 400 for i in errors["items"])


def test_request_logs_detail_engine_and_policy(admin_client):
    c = admin_client
    request_id, user_id = seed(c)
    login_admin(c)
    page = c.get("/api/admin/logs/requests", params={"profile": "elderly", "q": "하단"}).json()
    assert page["total"] == 2 and page["items"][0]["n_results"] == 3
    chosen = next(i for i in page["items"] if i["id"] == request_id)
    assert chosen["chosen_rank"] == 3 and chosen["user"]["nickname"] == "관리테스트"
    assert c.get("/api/admin/logs/requests", params={"personalized": "true"}).json()["total"] == 1
    assert c.get("/api/admin/logs/requests", params={"status": "no_route"}).json()["total"] == 0

    detail = c.get(f"/api/admin/logs/requests/{request_id}").json()
    assert len(detail["routes"]) == 3 and detail["choice"]["shown_rank"] == 3
    assert detail["engine_run"]["aco"]["iterations"] > 0 and detail["engine_run"]["corridor_nodes"] > 0
    assert detail["policy_update"]["updates_after"] == 1 and detail["policy_update"]["weights_after"] != detail["policy_update"]["weights_before"]
    assert c.get("/api/admin/logs/requests/00000000-0000-0000-0000-000000000000").status_code == 404
    assert c.get("/api/admin/logs/requests/not-a-uuid").status_code == 422

    engine = c.get("/api/admin/logs/engine").json()
    assert engine["total"] == 2 and engine["items"][0]["origin_name"] == "서면역"
    choices = c.get("/api/admin/logs/choices", params={"user_id": user_id}).json()
    assert choices["total"] == 1 and choices["items"][0]["learned"] is True
    updates = c.get("/api/admin/logs/policy-updates", params={"user_id": user_id}).json()
    assert updates["total"] == 1 and updates["items"][0]["shown_rank"] == 3
    c.get("/api/place/search", params={"query": "서면"})
    assert c.get("/api/admin/logs/places", params={"q": "서면"}).json()["total"] == 1


def test_users_list_detail_and_reset(admin_client):
    c = admin_client
    _, user_id = seed(c)
    login_admin(c)
    users = c.get("/api/admin/users", params={"sort": "requests"}).json()
    assert users["total"] == 1 and users["providers"] == [{"provider": "dev", "count": 1}]
    u = users["items"][0]
    assert u["id"] == user_id and u["requests"] == 2 and u["choices"] == 1 and u["updates"] == 1 and u["summary"]
    assert c.get("/api/admin/users", params={"q": "없는사람"}).json()["total"] == 0

    detail = c.get(f"/api/admin/users/{user_id}").json()
    assert detail["stats"]["requests"] == 2 and detail["stats"]["personalized_requests"] == 1
    assert detail["policy"]["updates"] == 1 and len(detail["policy_history"]) == 1 and len(detail["recent_requests"]) == 2
    assert detail["stats"]["profiles"] == [{"profile": "elderly", "label": "고령자", "count": 2}]

    assert c.delete(f"/api/admin/users/{user_id}/policy").json() == {"ok": True, "reset": True}
    assert c.get(f"/api/admin/users/{user_id}").json()["policy"]["updates"] == 0
    assert c.get("/api/admin/users/00000000-0000-0000-0000-000000000000").status_code == 404
    reset_log = c.get("/api/admin/logs/access", params={"kind": "admin"}).json()["items"]
    assert any((i["detail"] or "").startswith("reset_policy:") for i in reset_log)


def test_overview_analytics_preferences_and_export(admin_client):
    c = admin_client
    _, user_id = seed(c)
    login_admin(c)
    ov = c.get("/api/admin/overview").json()
    k = ov["kpis"]
    assert k["requests_total"] == 2 and k["users_total"] == 1 and k["choices_7d"] == 1 and k["learned_users"] == 1
    assert k["choose_rate_7d"] == 0.5 and k["personalized_share_7d"] == 0.5
    assert len(ov["series"]) == 30 and ov["series"][-1]["requests"] == 2
    assert ov["profile_share"] == [{"profile": "elderly", "label": "고령자", "count": 2}]
    assert len(ov["recent_requests"]) == 2 and ov["recent_auth"]

    usage = c.get("/api/admin/analytics/usage", params={"days": 7}).json()
    assert usage["total_requests"] == 2 and len(usage["daily"]) == 7 and sum(h["count"] for h in usage["hourly"]) == 2
    assert usage["status_share"] == [{"status": "ok", "count": 2}] and usage["prefer_shade"] == {"on": 0, "off": 2}

    quality = c.get("/api/admin/analytics/quality").json()
    assert quality["choose_rate"] == 0.5 and quality["by_shown_rank"][2] == {"rank": 3, "shown": 2, "chosen": 1, "rate": 0.5}
    assert quality["compare"]["plain"]["choices"] == 1 and quality["per_profile"][0]["profile"] == "elderly"
    assert quality["badges"] and quality["by_engine_rank"]

    spatial = c.get("/api/admin/analytics/spatial").json()
    assert spatial["top_origins"][0]["name"] == "서면역" and spatial["top_pairs"][0]["count"] == 2
    assert spatial["top_stations"] and spatial["facilities"]

    engine = c.get("/api/admin/analytics/engine").json()
    assert engine["summary"]["runs"] == 2 and engine["summary"]["engine_p50_ms"] is not None and engine["per_profile"]

    prefs = c.get("/api/admin/preferences").json()
    assert prefs["learned_users"] == 1 and len(prefs["per_feature"]) == 10 and prefs["users"][0]["user"]["id"] == user_id
    assert prefs["labels"]

    for kind in ("requests", "choices", "users", "access", "engine"):
        r = c.get(f"/api/admin/export/{kind}.csv")
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
        assert len(r.text.splitlines()) >= 2, kind
    assert c.get("/api/admin/export/nope.csv").status_code == 404
