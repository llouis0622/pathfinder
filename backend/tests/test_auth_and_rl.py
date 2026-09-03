"""로그인(카카오 콜백·데모 로그인·세션)과 경로 선택 → 개인화 재정렬 API 테스트."""
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ROUTE_BODY = {
    "origin": {"lat": 35.15, "lng": 129.06, "name": "출발"},
    "destination": {"lat": 35.1536, "lng": 129.0726, "name": "도착"},
    "profile": "elderly",
}


@pytest.fixture
def auth_client(external):
    cfg = Settings(database_url="sqlite+aiosqlite:///:memory:", engine_url="http://engine:8001", kakao_client_id="kakao-rest-key",
                   naver_client_id="naver-id", naver_client_secret="naver-secret", allow_dev_login=True,
                   personalization_epsilon=0.0, jwt_secret="test-secret", frontend_url="http://front.test")
    with TestClient(create_app(cfg), follow_redirects=False) as c:
        yield c


def test_providers_and_login_redirect(auth_client):
    assert auth_client.get("/api/auth/providers").json() == {"providers": ["kakao", "naver"], "dev_login": True}
    r = auth_client.get("/api/auth/kakao/login")
    assert r.status_code == 302
    assert r.headers["location"].startswith("https://kauth.kakao.com/oauth/authorize?")
    assert "client_id=kakao-rest-key" in r.headers["location"] and "redirect_uri=" in r.headers["location"]
    assert "pf_oauth_state" in r.cookies
    assert auth_client.get("/api/auth/google/login").status_code == 404


def test_kakao_callback_creates_session(auth_client, external):
    login = auth_client.get("/api/auth/kakao/login")
    state = login.cookies["pf_oauth_state"]
    auth_client.cookies.set("pf_oauth_state", state)
    r = auth_client.get("/api/auth/kakao/callback", params={"code": "abc", "state": state})
    assert r.status_code == 302 and r.headers["location"] == "http://front.test?login=ok"
    assert "pf_session" in r.cookies
    auth_client.cookies.set("pf_session", r.cookies["pf_session"])
    me = auth_client.get("/api/auth/me").json()["user"]
    assert me["provider"] == "kakao" and me["nickname"] == "카카오사람"
    # state 불일치는 거부
    bad = auth_client.get("/api/auth/kakao/callback", params={"code": "abc", "state": "wrong"})
    assert bad.status_code == 400
    # 로그아웃
    auth_client.post("/api/auth/logout")
    auth_client.cookies.clear()
    assert auth_client.get("/api/auth/me").json() == {"user": None}


def test_naver_callback_profile_parsing(auth_client, external):
    state = auth_client.get("/api/auth/naver/login").cookies["pf_oauth_state"]
    auth_client.cookies.set("pf_oauth_state", state)
    r = auth_client.get("/api/auth/naver/callback", params={"code": "xyz", "state": state})
    assert r.status_code == 302 and "pf_session" in r.cookies
    auth_client.cookies.set("pf_session", r.cookies["pf_session"])
    assert auth_client.get("/api/auth/me").json()["user"]["nickname"] == "네이버사람"


def test_dev_login_is_hidden_without_flag(external):
    cfg = Settings(database_url="sqlite+aiosqlite:///:memory:", engine_url="http://engine:8001", allow_dev_login=False)
    with TestClient(create_app(cfg)) as c:
        assert c.post("/api/auth/dev/login").status_code == 404


def test_choice_learns_and_reranks_for_logged_in_user(auth_client, external):
    # 게스트: 선택은 기록되지만 학습은 없음
    first = auth_client.post("/api/route", json=ROUTE_BODY).json()
    assert first["personalized"] is False
    guest = auth_client.post(f"/api/route/{first['request_id']}/choose", json={"route_id": first["routes"][2]["id"]}).json()
    assert guest == {"recorded": True, "learned": False, "updates": 0, "summary": []}

    # 로그인
    me = auth_client.post("/api/auth/dev/login", params={"nickname": "테스터"})
    assert me.status_code == 200 and me.json()["provider"] == "dev"
    assert auth_client.get("/api/auth/me").json()["user"]["nickname"] == "테스터"

    # 3순위(도보 가장 김? 엔진 픽스처에서 3순위)를 반복 선택 → 정책 학습
    last_id = None
    for _ in range(6):
        res = auth_client.post("/api/route", json=ROUTE_BODY).json()
        third = next(r for r in res["routes"] if r.get("engine_rank", r["rank"]) == 3)
        chosen = auth_client.post(f"/api/route/{res['request_id']}/choose", json={"route_id": third["id"]}).json()
        assert chosen["recorded"] and chosen["learned"]
        last_id = res["request_id"]
    prefs = auth_client.get("/api/me/preferences").json()
    assert prefs["updates"] == 6 and len(prefs["summary"]) >= 1

    # 이제 검색 결과가 개인화되어 엔진 3순위가 1순위로 올라온다
    res = auth_client.post("/api/route", json=ROUTE_BODY).json()
    assert res["personalized"] is True and res["metadata"]["personalized"] is True
    assert res["routes"][0]["engine_rank"] == 3 and res["routes"][0]["rank"] == 1
    assert sorted(r["rank"] for r in res["routes"]) == [1, 2, 3]
    stored = auth_client.get(f"/api/route/{last_id}").json()
    assert len(stored["routes"]) == 3

    # 잘못된 route_id, 없는 요청
    assert auth_client.post(f"/api/route/{res['request_id']}/choose", json={"route_id": "nope"}).status_code == 422
    assert auth_client.post("/api/route/00000000-0000-0000-0000-000000000000/choose", json={"route_id": "route_1"}).status_code == 404

    # 초기화
    assert auth_client.delete("/api/me/preferences").json() == {"ok": True}
    assert auth_client.get("/api/me/preferences").json()["updates"] == 0
    assert auth_client.post("/api/route", json=ROUTE_BODY).json()["personalized"] is False


def test_preferences_require_login(auth_client):
    assert auth_client.get("/api/me/preferences").status_code == 401


def test_places_and_recent(auth_client):
    c = auth_client
    assert c.get("/api/me/places").status_code == 401
    r = c.post("/api/auth/dev/login", params={"nickname": "즐겨찾기"})
    c.cookies.set("pf_session", r.cookies["pf_session"])
    home = c.post("/api/me/places", json={"label": "집", "name": "우리집", "lat": 35.15, "lng": 129.06}).json()
    assert home["label"] == "집" and c.get("/api/me/places").json()[0]["name"] == "우리집"
    again = c.post("/api/me/places", json={"label": "집", "name": "새집", "lat": 35.16, "lng": 129.07}).json()
    assert again["id"] == home["id"] and again["name"] == "새집" and len(c.get("/api/me/places").json()) == 1
    c.post("/api/route", json=ROUTE_BODY)
    c.post("/api/route", json=ROUTE_BODY)
    c.post("/api/route", json={**ROUTE_BODY, "destination": {"lat": 35.2, "lng": 129.1, "name": "다른 곳"}})
    recent = c.get("/api/me/recent").json()
    assert len(recent) == 2 and recent[0]["destination"]["name"] == "다른 곳" and recent[1]["origin"]["name"] == "출발"
    assert c.delete(f"/api/me/places/{home['id']}").json() == {"ok": True}
    assert c.get("/api/me/places").json() == []
    assert c.delete(f"/api/me/places/{home['id']}").status_code == 404
