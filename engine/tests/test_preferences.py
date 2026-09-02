"""선호(경사 회피 기본, 그늘 우선 선택)가 비용과 경로에 미치는 영향."""
from datetime import datetime

import numpy as np
import pytest

from app.cost.model import compute_costs
from app.cost.profiles import get_profile
from app.graph.model import Graph
from app.pipeline.synthetic import _latlng
from app.routes.schemas import LatLng, Preferences, SearchOptions, SearchRequest
from app.search.pipeline import search_routes


def _walk(edges):
    nodes = [{"id": i, "lat": 35.0, "lng": 129.0 + i * 0.001} for i in range(len(edges) + 1)]
    recs = [{"id": i, "source": i, "target": i + 1, "kind": "walk", "mode": "walk", "length_m": 100.0, **a} for i, a in enumerate(edges)]
    return Graph.from_records(nodes, recs)


def test_avoid_slope_scales_cost_with_grade_by_default():
    g = _walk([{"grade_pct": 0.0}, {"grade_pct": 4.0}, {"grade_pct": 4.0, "max_grade_pct": 8.0}])
    p = get_profile("elderly")
    on = compute_costs(g, p)                                    # 기본값 avoid_slope=True
    off = compute_costs(g, p, avoid_slope=False)
    assert on.cost[0] == pytest.approx(off.cost[0])             # 평지는 동일
    assert on.cost[1] > off.cost[1]
    assert on.cost[2] > on.cost[1]                              # 구간 최대 경사가 크면 더 비싸다
    assert on.time_s[1] == pytest.approx(off.time_s[1])         # 이동 시간은 그대로 (비용만 가중)
    assert on.cost[1] / off.cost[1] == pytest.approx(1 + p.slope_avoid_gain * 4.0)


def test_prefer_shade_only_when_shade_computed():
    g = _walk([{}, {}, {"indoor": True}])
    p = get_profile("wheelchair")
    shade = np.array([0.0, 1.0, 0.0])
    base = compute_costs(g, p, shade_ratio=shade, prefer_shade=False)
    pref = compute_costs(g, p, shade_ratio=shade, prefer_shade=True)
    assert pref.cost[0] == pytest.approx(base.cost[0] * (1 + p.shade_prefer_gain))
    assert pref.cost[1] == pytest.approx(base.cost[1])          # 완전 그늘
    assert pref.cost[2] == pytest.approx(base.cost[2])          # 실내
    off = compute_costs(g, p, shade_ratio=shade, prefer_shade=True, shade_available=False)
    assert off.cost[0] == pytest.approx(base.cost[0])           # 그늘 계산 불가(야간)면 무효


def _req(**kw):
    o, d = _latlng(4, 0), _latlng(12, 23)
    return SearchRequest(origin=LatLng(lat=o[0], lng=o[1]), destination=LatLng(lat=d[0], lng=d[1]), profile="elderly",
                         departure_at=datetime(2026, 8, 3, 15, 0), options=SearchOptions(seed=11, k=3), **kw)


def test_default_search_prefers_gentler_routes_than_slope_agnostic(store):
    default = search_routes(store, _req())
    agnostic = search_routes(store, _req(preferences=Preferences(avoid_slope=False)))
    assert default.metadata.preferences == {"avoid_slope": True, "prefer_shade": False}
    assert default.routes and agnostic.routes
    assert default.routes[0].features.avg_grade_pct <= agnostic.routes[0].features.avg_grade_pct + 1e-6


def test_prefer_shade_increases_top_route_shade(store):
    plain = search_routes(store, _req())
    shady = search_routes(store, _req(preferences=Preferences(prefer_shade=True)))
    assert shady.metadata.shade_status == "computed"
    assert shady.metadata.preferences["prefer_shade"] is True
    assert (shady.routes[0].features.shade_ratio or 0) >= (plain.routes[0].features.shade_ratio or 0)


def test_departure_defaults_to_now(store):
    o, d = _latlng(8, 0), _latlng(8, 23)
    res = search_routes(store, SearchRequest(origin=LatLng(lat=o[0], lng=o[1]), destination=LatLng(lat=d[0], lng=d[1]), profile="elderly",
                                             options=SearchOptions(seed=1)))
    assert res.metadata.departure_at is not None
    assert res.metadata.shade_status in ("computed", "not_daylight")
