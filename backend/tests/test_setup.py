"""설정 상태 점검과 DATABASE_URL 정규화."""
from fastapi.testclient import TestClient

from app import admin
from app.config import Settings, async_postgres_url
from app.main import create_app
from app.services import setup


def test_database_url_normalization():
    assert async_postgres_url("postgresql://u:p@h/d") == "postgresql+asyncpg://u:p@h/d"
    assert async_postgres_url("postgres://u:p@h/d") == "postgresql+asyncpg://u:p@h/d"
    assert async_postgres_url("postgresql+asyncpg://u:p@h/d") == "postgresql+asyncpg://u:p@h/d"
    assert async_postgres_url("sqlite+aiosqlite:///:memory:") == "sqlite+aiosqlite:///:memory:"
    assert Settings(database_url="postgresql://u:p@h/d", _env_file=None).database_url == "postgresql+asyncpg://u:p@h/d"


def test_setup_items_flag_missing_and_degraded():
    cfg = Settings(database_url="sqlite+aiosqlite:///:memory:", _env_file=None)   # 기본값: 키 없음
    engine = {"status": "ok", "detail": {"graph": {"nodes": 10, "edges": 20, "sample": True, "source": "../data/samples/grid_city.npz"}}}
    items = {i["key"]: i for i in setup.setup_items(cfg, engine, alert_webhook=False)}
    assert items["graph"]["status"] == "degraded" and "샘플" in items["graph"]["detail"]
    assert items["jwt"]["status"] == "missing" and items["admin"]["status"] == "missing"
    assert items["places"]["status"] == "degraded" and items["weather"]["status"] == "ok"
    assert items["login_kakao"]["status"] == "missing" and items["https"]["status"] == "degraded"
    s = setup.summarize(list(items.values()))
    assert s["ready_for_production"] is False and s["runnable"] is False and "jwt" in s["missing"]

    good = Settings(database_url="postgresql://u:p@h/d", jwt_secret="x" * 40, admin_password="pw", kakao_rest_api_key="k", kakao_client_id="c",
                    naver_client_id="n", naver_client_secret="s", public_base_url="https://pf.example.com", allow_dev_login=False, _env_file=None)
    engine_ok = {"status": "ok", "detail": {"graph": {"nodes": 1, "edges": 1, "sample": False, "source": "postgis_memory", "resolved_from": "PostGIS 에 적재된 그래프"}}}
    s2 = setup.summarize(setup.setup_items(good, engine_ok, alert_webhook=True))
    assert s2["ready_for_production"] is True and s2["missing"] == [] and s2["degraded"] == []
    down = {i["key"]: i for i in setup.setup_items(good, {"status": "down", "detail": "ConnectError"})}
    assert down["engine"]["status"] == "missing" and down["graph"]["status"] == "missing"


def test_health_and_admin_setup_endpoint(external):
    admin.reset_failures()
    cfg = Settings(database_url="sqlite+aiosqlite:///:memory:", engine_url="http://engine:8001", admin_password="secret-pw", _env_file=None)
    with TestClient(create_app(cfg)) as c:
        h = c.get("/health").json()
        assert h["features"]["runnable"] is False and "jwt" in h["features"]["missing"] and "admin" not in h["features"]["missing"]
        r = c.post("/api/admin/login", json={"password": "secret-pw"})
        c.cookies.set("pf_admin", r.cookies["pf_admin"])
        s = c.get("/api/admin/setup").json()
        keys = [i["key"] for i in s["items"]]
        assert "alerts" in keys and s["summary"]["counts"]["ok"] >= 2
