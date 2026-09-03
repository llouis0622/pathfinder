import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import http
from app.config import Settings
from app.main import create_app
from app.services import places, weather

FIXTURES = Path(__file__).parent / "fixtures"
ENGINE_RESPONSE = json.loads((FIXTURES / "engine_search.json").read_text(encoding="utf-8"))


class FakeExternal:
    """호스트별 가짜 응답. 테스트가 속성을 바꿔 시나리오를 조정한다."""

    def __init__(self) -> None:
        self.engine_status = 200
        self.engine_detail = "경로 없음"
        self.engine_calls: list[dict] = []
        self.kakao_docs: list[dict] = [
            {"id": "1", "place_name": "부산역", "road_address_name": "부산 동구 중앙대로 206", "x": "129.0403", "y": "35.1151", "category_name": "교통 > 기차역"},
        ]
        self.kakao_status = 200
        self.open_meteo = {
            "current": {"time": "2026-08-03T13:00", "temperature_2m": 31.0, "apparent_temperature": 34.2, "precipitation": 0.0,
                        "wind_speed_10m": 3.0, "weather_code": 1},
            "hourly": {"time": ["2026-08-03T13:00", "2026-08-03T14:00", "2036-01-01T09:00"],
                       "temperature_2m": [31.0, 32.0, -3.0], "apparent_temperature": [34.2, 35.0, -8.0],
                       "precipitation": [0.0, 2.0, 0.0], "wind_speed_10m": [3.0, 4.0, 12.0], "weather_code": [1, 61, 71]},
        }
        self.open_meteo_air = {"current": {"pm10": 40.0}, "hourly": {"time": ["2036-01-01T09:00"], "pm10": [95.0]}}
        self.open_meteo_fail = False
        self.webhook_calls: list[dict] = []
        self.webhook_status = 200
        self.engine_health_ok = True

    def handler(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        path = request.url.path
        if host in ("engine", "localhost", "127.0.0.1") and path == "/api/search":
            self.engine_calls.append(json.loads(request.content))
            if self.engine_status != 200:
                return httpx.Response(self.engine_status, json={"detail": self.engine_detail})
            return httpx.Response(200, json=ENGINE_RESPONSE)
        if host in ("engine", "localhost", "127.0.0.1") and path == "/api/profiles":
            return httpx.Response(200, json=[{"id": "wheelchair", "label": "휠체어 이용자", "description": "d", "speed_mps": 1.0}])
        if host in ("engine", "localhost", "127.0.0.1") and path == "/health":
            if not self.engine_health_ok:
                return httpx.Response(503, text="down")
            return httpx.Response(200, json={"status": "ok"})
        if host == "hooks.example.test":
            self.webhook_calls.append(json.loads(request.content))
            return httpx.Response(self.webhook_status, text="ok" if self.webhook_status < 300 else "invalid_token")
        if host in ("engine", "localhost", "127.0.0.1") and path == "/api/nearest-edge":
            if float(request.url.params["lat"]) > 80:
                return httpx.Response(422, json={"detail": "반경 안에 보행 엣지가 없습니다"})
            return httpx.Response(200, json={"edge_id": 1234, "kind": "vertical", "distance_m": 4.2, "stairs": 0, "elevator": 1, "kerb": "", "name": "A역"})
        if host in ("engine", "localhost", "127.0.0.1") and path == "/api/stats":
            return httpx.Response(200, json={"nodes": {"total": 418, "by_kind": {"walk": 400}}, "edges": {"total": 1540, "by_kind": {}},
                                             "walk": {"edges": 1400, "grade_coverage": 0.9}, "vertical": {"elevator": {"yes": 10, "no": 2, "unknown": 3}},
                                             "buildings": {"total": 31, "height_known": 30, "height_coverage": 0.97},
                                             "connectivity": {"components": 1, "largest_share": 1.0, "isolated_walk_nodes": 0}, "source": "grid_city"})
        if host in ("engine", "localhost", "127.0.0.1") and path == "/api/tiles/meta":
            return httpx.Response(200, json={"minzoom": 14, "extent": 4096, "layers": {"edges": "e"}})
        if host in ("engine", "localhost", "127.0.0.1") and path.startswith("/api/tiles/"):
            z = int(path.split("/")[3])
            if z < 14:
                return httpx.Response(204)
            if z > 22:
                return httpx.Response(404, json={"detail": "bad"})
            return httpx.Response(200, content=b"\x1a\x05tile", headers={"content-type": "application/vnd.mapbox-vector-tile"})
        if host in ("engine", "localhost", "127.0.0.1") and path == "/api/shade":
            q = request.url.params
            if float(q["max_lat"]) - float(q["min_lat"]) > 0.05:
                return httpx.Response(422, json={"detail": "지도를 더 확대하세요"})
            return httpx.Response(200, json={"status": "computed", "ratios": {"1": 0.5, "2": 0.0}, "at": q.get("at")})
        if host == "kauth.kakao.com" and path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "kakao-token", "token_type": "bearer"})
        if host == "kapi.kakao.com" and path == "/v2/user/me":
            assert request.headers.get("authorization") == "Bearer kakao-token"
            return httpx.Response(200, json={"id": 12345, "kakao_account": {"profile": {"nickname": "카카오사람", "thumbnail_image_url": "http://img/k.png"}}})
        if host == "nid.naver.com" and path == "/oauth2.0/token":
            return httpx.Response(200, json={"access_token": "naver-token"})
        if host == "openapi.naver.com" and path == "/v1/nid/me":
            return httpx.Response(200, json={"resultcode": "00", "response": {"id": "n-1", "nickname": "네이버사람", "profile_image": ""}})
        if host == "dapi.kakao.com":
            if self.kakao_status != 200:
                return httpx.Response(self.kakao_status, json={"message": "unauthorized"})
            return httpx.Response(200, json={"documents": self.kakao_docs})
        if host == "api.open-meteo.com":
            if self.open_meteo_fail:
                return httpx.Response(500, text="boom")
            return httpx.Response(200, json=self.open_meteo)
        if host == "air-quality-api.open-meteo.com":
            return httpx.Response(200, json=self.open_meteo_air)
        return httpx.Response(404, text=f"unhandled {request.url}")


@pytest.fixture
def external():
    fake = FakeExternal()
    http.override_transport = httpx.MockTransport(fake.handler)
    weather.clear_cache()
    places._index = None
    yield fake
    http.override_transport = None


@pytest.fixture
def client(external):
    cfg = Settings(database_url="sqlite+aiosqlite:///:memory:", engine_url="http://engine:8001", kakao_rest_api_key="test-key",
                   weather_provider="open_meteo")
    with TestClient(create_app(cfg)) as c:
        yield c


@pytest.fixture
def client_no_kakao(external):
    cfg = Settings(database_url="sqlite+aiosqlite:///:memory:", engine_url="http://engine:8001", kakao_rest_api_key="")
    with TestClient(create_app(cfg)) as c:
        yield c
