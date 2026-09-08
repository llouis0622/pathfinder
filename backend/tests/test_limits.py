"""IP 당 검색 한도(429)와 엔진 동시성 게이트(503), 관리자 한도 설정."""
import asyncio

from fastapi.testclient import TestClient

from app import admin
from app.config import Settings
from app.main import create_app
from app.services import limits

ROUTE_BODY = {"origin": {"lat": 35.15, "lng": 129.06, "name": "서면역"}, "destination": {"lat": 35.1536, "lng": 129.0726, "name": "하단역"},
              "profile": "elderly"}


def test_rate_limiter_and_retry_after():
    rl = limits.RateLimiter(2)
    assert rl.allow("a", now=100.0) and rl.allow("a", now=101.0) and not rl.allow("a", now=102.0)
    assert rl.retry_after("a", now=102.0) == 58 and rl.rejected == 1
    assert rl.allow("b", now=102.0)                       # 다른 IP 는 독립
    assert rl.allow("a", now=161.0)                       # 창이 지나면 다시 허용
    assert limits.RateLimiter(0).allow("x")               # 0 = 끔


def test_engine_gate_times_out():
    async def run():
        gate = limits.EngineGate(1, 0.05)
        assert await gate.acquire() is True
        assert await gate.acquire() is False and gate.rejected == 1
        gate.release()
        assert await gate.acquire() is True and gate.inflight == 1
    asyncio.run(run())


def test_route_limit_and_admin_settings(external):
    admin.reset_failures()
    cfg = Settings(database_url="sqlite+aiosqlite:///:memory:", engine_url="http://engine:8001", admin_password="secret-pw",
                   jwt_secret="test-secret-0123456789-abcdefghijklmnop", search_cache_ttl_s=0, route_rate_limit_per_minute=2, _env_file=None)
    with TestClient(create_app(cfg)) as c:
        assert c.post("/api/route", json=ROUTE_BODY).status_code == 200
        assert c.post("/api/route", json=ROUTE_BODY).status_code == 200
        r = c.post("/api/route", json=ROUTE_BODY)
        assert r.status_code == 429 and "Retry-After" in r.headers
        # 다른 IP(프록시가 붙인 마지막 항목) 는 허용
        assert c.post("/api/route", json=ROUTE_BODY, headers={"x-forwarded-for": "1.1.1.1, 203.0.113.7"}).status_code == 200
        login = c.post("/api/admin/login", json={"password": "secret-pw"})
        c.cookies.set("pf_admin", login.cookies["pf_admin"])
        got = c.get("/api/admin/limits").json()
        assert got["limits"]["route_per_minute"] == 2 and got["stats"]["route_rejected"] == 1 and got["defaults"]["engine_concurrency"] == 4
        saved = c.put("/api/admin/limits", json={"route_per_minute": 0, "engine_concurrency": 2}).json()
        assert saved["limits"]["route_per_minute"] == 0 and saved["limits"]["engine_concurrency"] == 2
        assert c.post("/api/route", json=ROUTE_BODY).status_code == 200     # 즉시 적용: 한도 없음
        assert c.put("/api/admin/limits", json={"engine_concurrency": 999}).status_code == 422
