"""RL 개인화 단위 테스트."""
import random

import pytest

from app.services.personalization import FEATURES, Policy, normalized_features, rerank, scores, softmax, update


def _route(i, duration, walk, shade=0.0, transfers=0, grade=1.0):
    return {"id": f"route_{i}", "rank": i, "features": {
        "total_duration_s": duration, "walk_distance_m": walk, "transfers": transfers, "max_grade_pct": grade, "stairs_count": 0,
        "shade_ratio": shade, "unshaded_walk_m": walk * (1 - shade), "unverified_vertical_count": 0, "wait_duration_s": 120,
        "ride_duration_s": 400,
    }}


ROUTES = [_route(1, 1200, 900, shade=0.1), _route(2, 1400, 400, shade=0.3), _route(3, 1700, 300, shade=0.8, transfers=1)]


def test_normalized_features_are_centered_minmax():
    phis = normalized_features(ROUTES)
    assert phis[0]["duration"] == pytest.approx(-0.5) and phis[2]["duration"] == pytest.approx(0.5)
    assert phis[0]["walk"] == pytest.approx(0.5) and phis[2]["walk"] == pytest.approx(-0.5)
    assert all(phi["stairs"] == 0.0 for phi in phis)          # 모두 같으면 0


def test_untrained_policy_keeps_engine_order():
    p = Policy()
    s = scores(p, ROUTES)
    assert s == sorted(s, reverse=True)
    rr = rerank(p, ROUTES)
    assert not rr.applied and [r["rank"] for r in rr.routes] == [1, 2, 3]


def test_update_moves_weights_toward_chosen_route():
    p = Policy()
    p2 = update(p, ROUTES, "route_3")     # 가장 도보가 짧고 그늘이 많은 3순위를 골랐다
    assert p2.updates == 1
    assert p2.weights["walk"] < 0          # 도보 적은 쪽 선호
    assert p2.weights["shade"] > 0         # 그늘 선호
    assert p2.weights["duration"] > 0      # 오래 걸려도 괜찮음
    assert set(p2.weights) == set(FEATURES)
    same = update(p, ROUTES, "nope")
    assert same.updates == 0


def test_repeated_choices_rerank_and_summarise():
    p = Policy()
    for _ in range(6):
        p = update(p, ROUTES, "route_3")
    rr = rerank(p, ROUTES, rng=random.Random(1), epsilon=0.0)
    assert rr.applied and not rr.explored
    assert rr.routes[0]["id"] == "route_3" and rr.routes[0]["rank"] == 1 and rr.routes[0]["engine_rank"] == 3
    assert sum(rr.propensities.values()) == pytest.approx(1.0, abs=1e-3)
    assert rr.propensities["route_3"] > rr.propensities["route_1"]
    assert "그늘 많은 길 선호" in p.summary() or "도보 적은 길 선호" in p.summary()


def test_exploration_samples_from_policy_and_keeps_all_routes():
    p = Policy()
    p = update(p, ROUTES, "route_2")
    seen = set()
    for seed in range(40):
        rr = rerank(p, ROUTES, rng=random.Random(seed), epsilon=1.0)
        assert rr.applied and rr.explored
        assert sorted(r["id"] for r in rr.routes) == ["route_1", "route_2", "route_3"]
        assert [r["rank"] for r in rr.routes] == [1, 2, 3]
        seen.add(rr.routes[0]["id"])
    assert len(seen) >= 2


def test_softmax_and_weight_clipping():
    assert softmax([0.0, 0.0]) == [0.5, 0.5]
    p = Policy(weights={f: 10.0 for f in FEATURES}, updates=5)
    p2 = update(p, ROUTES, "route_1")
    assert all(abs(w) <= 3.0 for w in p2.weights.values())
    assert Policy.from_dict(p2.to_dict()).weights == p2.weights
