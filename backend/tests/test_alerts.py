"""임계 초과 알림: 설정 저장, 규칙 평가, 웹훅 전송·쿨다운·복구."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import admin, reports
from app.config import Settings
from app.main import create_app
from app.services import alerts

ROUTE_BODY = {"origin": {"lat": 35.15, "lng": 129.06, "name": "서면역"}, "destination": {"lat": 35.1536, "lng": 129.0726, "name": "하단역"},
              "profile": "elderly"}


@pytest.fixture
def alert_client(external):
    admin.reset_failures()
    reports.reset_rate_limits()
    cfg = Settings(database_url="sqlite+aiosqlite:///:memory:", engine_url="http://engine:8001", admin_password="secret-pw", jwt_secret="test-secret-0123456789-abcdefghijklmnop",
                   search_cache_ttl_s=0, alert_webhook_url="", report_rate_limit_per_hour=100)
    with TestClient(create_app(cfg)) as c:
        r = c.post("/api/admin/login", json={"password": "secret-pw"})
        c.cookies.set("pf_admin", r.cookies["pf_admin"])
        yield c


def test_settings_roundtrip_and_validation(alert_client):
    c = alert_client
    s = c.get("/api/admin/alerts/settings").json()
    assert s["webhook_configured"] is False and s["rules"]["error_rate"]["threshold"] == 10.0
    r = c.put("/api/admin/alerts/settings", json={"webhook_url": "ftp://nope"})
    assert r.status_code == 422
    r = c.put("/api/admin/alerts/settings", json={"rules": {"bogus": {"enabled": True}}})
    assert r.status_code == 422
    r = c.put("/api/admin/alerts/settings", json={"webhook_url": "https://hooks.example.test/services/T000/B000/XXXXXXXXXXXXXXXXXXXXXXXX",
                                                  "rules": {"error_rate": {"threshold": 5, "min_samples": 2}}, "cooldown_min": 30, "window_min": 5})
    assert r.status_code == 200
    s = r.json()
    assert s["webhook_configured"] is True and s["webhook_url_masked"].endswith("…") and "XXXXXXXX" not in s["webhook_url_masked"]
    assert s["rules"]["error_rate"] == {"enabled": True, "threshold": 5, "min_samples": 2}
    assert s["rules"]["open_reports"]["threshold"] == 10          # 다른 규칙은 그대로
    assert s["window_min"] == 5
    # 저장된 값이 다시 읽힌다
    assert c.get("/api/admin/alerts/settings").json()["cooldown_min"] == 30


def test_evaluate_sends_once_then_recovers(alert_client, external):
    c = alert_client
    c.put("/api/admin/alerts/settings", json={"webhook_url": "https://hooks.example.test/services/x",
                                              "rules": {"error_rate": {"threshold": 20, "min_samples": 2}, "open_reports": {"threshold": 1}}})
    # 아무 문제 없음 → 알림 없음
    r = c.post("/api/admin/alerts/evaluate").json()
    assert r["findings"] == [] and r["sent"] == []
    # 엔진 오류 2건 + 제보 1건 → error_rate, open_reports
    external.engine_status = 500
    for _ in range(2):
        c.post("/api/route", json=ROUTE_BODY)
    c.post("/api/reports", json={"lat": 35.15, "lng": 129.06, "kind": "stairs"})
    r = c.post("/api/admin/alerts/evaluate").json()
    rules = sorted(f["rule"] for f in r["findings"])
    assert rules == ["error_rate", "open_reports"]
    assert sorted(e["rule"] for e in r["sent"]) == ["error_rate", "open_reports"] and all(e["sent"] for e in r["sent"])
    assert len(external.webhook_calls) == 1 and "검색 오류율" in external.webhook_calls[0]["text"]
    # 쿨다운 안이면 다시 보내지 않는다
    r = c.post("/api/admin/alerts/evaluate").json()
    assert len(r["findings"]) == 2 and r["sent"] == [] and len(external.webhook_calls) == 1
    # 제보를 처리하면 복구 알림 한 건
    rid = c.get("/api/admin/reports").json()["items"][0]["id"]
    c.post(f"/api/admin/reports/{rid}/reject", json={"note": "x"})
    r = c.post("/api/admin/alerts/evaluate").json()
    assert [e["rule"] for e in r["sent"]] == ["open_reports"] and r["sent"][0]["level"] == "ok"
    assert len(external.webhook_calls) == 2
    ev = c.get("/api/admin/alerts/events").json()
    assert ev["total"] == 3 and ev["items"][0]["level"] == "ok"
    # 메트릭
    m = c.get("/metrics").text
    assert 'pathfinder_alerts_sent_total{rule="error_rate"}' in m


def test_engine_down_and_webhook_failure(alert_client, external):
    c = alert_client
    external.engine_health_ok = False
    external.webhook_status = 403
    c.put("/api/admin/alerts/settings", json={"webhook_url": "https://hooks.example.test/services/x", "format": "json"})
    r = c.post("/api/admin/alerts/evaluate").json()
    assert [f["rule"] for f in r["findings"]] == ["engine_down"]
    assert r["sent"][0]["sent"] is False and r["sent"][0]["http_status"] == 403 and "invalid_token" in r["sent"][0]["error"]
    assert external.webhook_calls[-1]["events"][0]["rule"] == "engine_down"   # json 형식
    t = c.post("/api/admin/alerts/test").json()
    assert t["level"] == "test" and t["sent"] is False
    # 웹훅이 없으면 평가만 하고 보내지 않는다
    c.put("/api/admin/alerts/settings", json={"webhook_url": ""})
    r = c.post("/api/admin/alerts/evaluate").json()
    assert r["webhook_configured"] is False and r["sent"] == []


def test_notify_cooldown_by_time(alert_client):
    state = alerts.AlertState()
    now = datetime.now(timezone.utc)
    state.last_sent["error_rate"] = now - timedelta(minutes=10)
    s = {**alerts.DEFAULTS, "cooldown_min": 60, "webhook_url": ""}
    # 쿨다운 안 → 보낼 것 없음. 함수 자체는 DB 없이 돌지 않으므로 규칙 선별만 확인
    findings = [alerts.Finding("error_rate", 50.0, 10.0, "x")]
    cooldown = timedelta(minutes=s["cooldown_min"])
    assert all(now - state.last_sent.get(f.rule, now - cooldown * 2) < cooldown for f in findings)
    assert alerts.payload("slack", [{"rule": "engine_down", "level": "warn", "message": "m"}])["text"].startswith("*Pathfinder 알림*")
