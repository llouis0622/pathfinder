"""동시 탐색 게이트: 상한을 넘으면 기다렸다가 503."""
from fastapi.testclient import TestClient

from app.api.routes import SearchGate
from app.config import Settings
from app.main import create_app


def test_gate_counts_and_rejects():
    g = SearchGate(1, 0.05)
    assert g.acquire() and g.inflight == 1
    assert not g.acquire() and g.rejected == 1
    g.release()
    assert g.inflight == 0 and g.acquire()
    assert g.stats()["limit"] == 1


def test_search_returns_503_when_gate_full():
    cfg = Settings(graph_source="file", search_queue_timeout_s=0.05, _env_file=None)
    with TestClient(create_app(config=cfg)) as c:
        gate: SearchGate = c.app.state.search_gate
        held = [gate.acquire() for _ in range(gate.limit)]        # 자리를 모두 차지
        assert all(held)
        body = {"origin": {"lat": 35.1536, "lng": 129.06}, "destination": {"lat": 35.1536, "lng": 129.0726}, "profile": "wheelchair"}
        r = c.post("/api/search", json=body)
        assert r.status_code == 503 and r.headers.get("retry-after") == "2"
        for _ in held:
            gate.release()
        assert c.post("/api/search", json=body).status_code == 200
