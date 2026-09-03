import numpy as np
import pytest

from app.cost.model import (
    BLOCK_KERB,
    BLOCK_LOW_FLOOR,
    BLOCK_SLOPE,
    BLOCK_STAIRS,
    BLOCK_VERTICAL,
    BLOCK_WIDTH,
    compute_costs,
    route_cost,
)
from app.cost.profiles import PROFILES, get_profile
from app.cost.weather import WeatherContext
from app.graph.model import Graph


def _graph(edges):
    nodes = [{"id": i, "lat": 35.0, "lng": 129.0 + i * 0.001} for i in range(len(edges) + 1)]
    recs = []
    for i, attrs in enumerate(edges):
        rec = {"id": i, "source": i, "target": i + 1, "kind": "walk", "mode": "walk", "length_m": 100.0}
        rec.update(attrs)
        recs.append(rec)
    return Graph.from_records(nodes, recs)


def test_flat_walk_time_uses_profile_speed():
    g = _graph([{}])
    for pid, p in PROFILES.items():
        r = compute_costs(g, p)
        assert r.time_s[0] == pytest.approx(100.0 / p.speed_mps)
        assert r.cost[0] == pytest.approx(r.time_s[0])


def test_slope_blocks_wheelchair_only():
    g = _graph([{"grade_pct": 12.0}, {"grade_pct": -12.0}, {"grade_pct": 4.0}])
    r = compute_costs(g, get_profile("wheelchair"))
    assert r.blocked[0] == BLOCK_SLOPE and r.blocked[1] == BLOCK_SLOPE and r.blocked[2] == 0
    assert np.isinf(r.cost[0]) and np.isfinite(r.cost[2])
    r2 = compute_costs(g, get_profile("elderly"))
    assert r2.n_blocked == 0
    # 오르막이 내리막보다, 급경사가 완경사보다 비싸다
    assert r2.cost[0] > r2.cost[1] > r2.cost[2]


def test_stairs_rules():
    g = _graph([{"stairs": True, "step_count": 20}, {"stairs": True, "ramp": True}, {"stairs": True, "handrail": True, "step_count": 20}])
    wc = compute_costs(g, get_profile("wheelchair"))
    assert wc.blocked[0] == BLOCK_STAIRS and wc.blocked[1] == 0
    el = compute_costs(g, get_profile("elderly"))
    assert el.n_blocked == 0
    base = 100.0 / get_profile("elderly").speed_mps
    assert el.cost[0] == pytest.approx(base + 25 + 3 * 20)
    vi = compute_costs(g, get_profile("visually_impaired"))
    assert vi.cost[2] < vi.cost[0]  # 난간이 있으면 절반


def test_width_kerb_low_floor_vertical_blocks():
    g = _graph([
        {"width_m": 0.8}, {"width_m": 1.0}, {"crossing": "unmarked", "kerb": "raised"},
        {"kind": "vertical", "elevator": False, "escalator": False, "length_m": 0.0},
        {"kind": "vertical", "elevator": None, "length_m": 0.0},
        {"kind": "board", "mode": "bus", "low_floor_ratio": 0.0, "headway_s": 600.0},
        {"kind": "board", "mode": "bus", "low_floor_ratio": 0.5, "headway_s": 600.0},
    ])
    r = compute_costs(g, get_profile("wheelchair"))
    assert r.blocked[0] == BLOCK_WIDTH and r.blocked[1] == 0
    assert r.blocked[2] == BLOCK_KERB
    assert r.blocked[3] == BLOCK_VERTICAL
    assert r.blocked[4] == 0 and r.unverified[4] and r.cost[4] == pytest.approx(90 + 600)
    assert r.blocked[5] == BLOCK_LOW_FLOOR
    # 저상 비율 0.5 → 기대 대기 두 배
    assert r.time_s[6] == pytest.approx(300 / 0.5 + 120)
    el = compute_costs(g, get_profile("elderly"))
    assert el.n_blocked == 0
    assert el.cost[3] == pytest.approx(150)


def test_surface_and_crossing_penalties():
    g = _graph([{"surface": "gravel"}, {"surface": "asphalt"}, {"crossing": "traffic_signals"}, {"crossing": "unmarked"}])
    for pid in ("wheelchair", "elderly", "visually_impaired"):
        r = compute_costs(g, get_profile(pid))
        assert r.cost[0] > r.cost[1]
    vi = compute_costs(g, get_profile("visually_impaired"))
    wc = compute_costs(g, get_profile("wheelchair"))
    assert vi.cost[3] - vi.cost[1] == pytest.approx(90)
    assert wc.cost[3] - wc.cost[1] == pytest.approx(15)


def test_weather_multipliers_only_outdoor_and_shade():
    g = _graph([{}, {"indoor": True}, {}])
    p = get_profile("elderly")
    hot = WeatherContext(feels_like_c=34.0)
    assert hot.heat and hot.heatwave
    shade = np.array([0.0, 0.0, 1.0])
    r = compute_costs(g, p, hot, shade)
    base = 100.0 / p.speed_mps
    assert r.cost[0] == pytest.approx(base * (1 + 1.2))   # h=0.6*2, 그늘 0
    assert r.cost[1] == pytest.approx(base)               # 실내
    assert r.cost[2] == pytest.approx(base)               # 그늘 100%
    rain = WeatherContext(precipitation_mm=3.0)
    assert rain.rain
    r2 = compute_costs(g, p, rain)
    assert r2.cost[0] == pytest.approx(base * 1.25)


def test_weather_flags_explicit_override():
    w = WeatherContext(temp_c=10.0, heatwave=True, flags_explicit=True)
    assert w.heat and w.heatwave and not w.rain
    assert "heatwave" in w.active_flags()


def test_route_cost_refunds_first_transfer_penalty():
    g = _graph([{"kind": "board", "mode": "subway", "headway_s": 600.0}, {"kind": "ride", "mode": "subway", "time_s": 300.0},
                {"kind": "alight", "mode": "subway"}])
    p = get_profile("elderly")
    r = compute_costs(g, p)
    total = float(r.cost.sum())
    assert route_cost([0, 1, 2], r, g) == pytest.approx(total - p.transfer_penalty_s)
    assert route_cost([1], r, g) == pytest.approx(300.0)
    assert route_cost([], r, g) == 0.0
