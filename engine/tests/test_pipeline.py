from datetime import datetime

import pytest

from app.cost.weather import WeatherContext
from app.pipeline.synthetic import _latlng
from app.routes.schemas import LatLng, SearchOptions, SearchRequest
from app.search.pipeline import NoRouteError, search_routes


def _req(profile, **kw):
    o = _latlng(8, 0)
    d = _latlng(8, 23)
    return SearchRequest(origin=LatLng(lat=o[0], lng=o[1]), destination=LatLng(lat=d[0], lng=d[1]), profile=profile, **kw)


@pytest.mark.parametrize("profile", ["wheelchair", "elderly", "walking_aid", "visually_impaired"])
def test_search_returns_three_distinct_valid_routes(store, profile):
    res = search_routes(store, _req(profile, options=SearchOptions(seed=5)))
    assert len(res.routes) == 3
    assert [r.rank for r in res.routes] == [1, 2, 3]
    assert len({tuple(map(tuple, r.path)) for r in res.routes}) == 3
    costs = [r.features.generalized_cost_s for r in res.routes]
    assert costs == sorted(costs)
    assert "fastest" in res.routes[0].badges or any("fastest" in r.badges for r in res.routes)
    for r in res.routes:
        assert r.total_duration_min > 0 and r.path[0] and r.legs
        assert r.path[0][0] == pytest.approx(_latlng(8, 0)[0], abs=1e-6)
        assert r.path[-1][0] == pytest.approx(_latlng(8, 23)[0], abs=1e-6)
        if profile == "wheelchair":
            assert r.features.stairs_count == 0
            assert all(leg.facility in ("elevator", "unknown") for leg in r.legs if leg.kind == "vertical")
    assert res.metadata.shade_status in ("computed", "not_daylight")
    assert res.metadata.elevation_resolution_m == 90


def test_shade_and_heat_change_costs_and_badges(store):
    noon = datetime(2026, 8, 3, 13, 0)
    hot = WeatherContext(temp_c=32.0, feels_like_c=34.0)
    res = search_routes(store, _req("elderly", departure_at=noon, weather=hot, options=SearchOptions(seed=5)))
    assert res.metadata.shade_status == "computed"
    assert res.metadata.solar_elevation_deg > 60
    assert "heatwave" in res.metadata.weather_flags
    assert any(r.features.shade_ratio is not None for r in res.routes)
    assert any("더위" in c for r in res.routes for c in r.cautions) or all(r.features.unshaded_walk_m <= 500 for r in res.routes)
    night = search_routes(store, _req("elderly", departure_at=datetime(2026, 8, 3, 23, 0), options=SearchOptions(seed=5)))
    assert night.metadata.shade_status == "not_daylight"


def test_walk_only_when_transit_unreachable(store):
    o = _latlng(8, 0)
    d = _latlng(8, 3)
    req = SearchRequest(origin=LatLng(lat=o[0], lng=o[1]), destination=LatLng(lat=d[0], lng=d[1]), profile="elderly",
                        options=SearchOptions(seed=1, k=2))
    res = search_routes(store, req)
    assert 1 <= len(res.routes) <= 2
    assert all(leg.kind == "walk" for leg in res.routes[0].legs)
    assert res.routes[0].features.transfers == 0


def test_same_node_raises(store):
    o = _latlng(8, 0)
    req = SearchRequest(origin=LatLng(lat=o[0], lng=o[1]), destination=LatLng(lat=o[0], lng=o[1]), profile="elderly")
    with pytest.raises(NoRouteError):
        search_routes(store, req)


def test_options_disable_ga_and_limit_iterations(store):
    res = search_routes(store, _req("visually_impaired", options=SearchOptions(seed=2, use_ga=False, aco_iterations=5, k=1)))
    assert res.metadata.ga == {"enabled": False}
    assert res.metadata.aco["iterations"] <= 5
    assert len(res.routes) == 1


def test_legs_are_consistent(store):
    res = search_routes(store, _req("elderly", options=SearchOptions(seed=9)))
    for r in res.routes:
        kinds = [leg.kind for leg in r.legs]
        assert kinds[0] == "walk" and kinds[-1] == "walk"
        walk_sum = sum(leg.distance_m for leg in r.legs if leg.kind == "walk")
        assert walk_sum == pytest.approx(r.walk_distance_m, abs=0.5)
        for leg in r.legs:
            if leg.kind == "ride":
                assert leg.stop_count >= 1 and leg.from_name and leg.to_name and leg.route_name
                assert leg.wait_s > 0
            if leg.kind == "walk":
                assert len(leg.segments) >= 1
                assert sum(s.distance_m for s in leg.segments) == pytest.approx(leg.distance_m, abs=0.5)
