from datetime import datetime, timezone

import numpy as np
import pytest

from app.features.shade import edge_shade_ratios
from app.features.solar import round_to_bucket, solar_position
from app.graph.model import Graph
from app.graph.store import Building


def test_solar_position_busan_summer_noon():
    az, el = solar_position(datetime(2026, 6, 21, 12, 30), 35.18, 129.08)
    assert 70 < el < 80
    assert 150 < az < 210
    az2, el2 = solar_position(datetime(2026, 6, 21, 3, 30, tzinfo=timezone.utc), 35.18, 129.08)
    assert el2 == pytest.approx(el, abs=1e-6)
    _, night = solar_position(datetime(2026, 6, 21, 1, 0), 35.18, 129.08)
    assert night < 0


def test_round_to_bucket():
    assert round_to_bucket(datetime(2026, 1, 1, 13, 14)).minute == 0
    assert round_to_bucket(datetime(2026, 1, 1, 13, 16)).minute == 30


def _street_graph():
    # 동서 방향 100 m 거리 두 개: 하나는 건물 바로 북쪽, 하나는 멀리
    nodes = [
        {"id": 1, "lat": 35.1000, "lng": 129.0000}, {"id": 2, "lat": 35.1000, "lng": 129.0011},
        {"id": 3, "lat": 35.1030, "lng": 129.0000}, {"id": 4, "lat": 35.1030, "lng": 129.0011},
        {"id": 5, "lat": 35.1000, "lng": 129.0000},
    ]
    edges = [
        {"id": 1, "source": 1, "target": 2, "kind": "walk", "length_m": 100},
        {"id": 2, "source": 3, "target": 4, "kind": "walk", "length_m": 100},
        {"id": 3, "source": 1, "target": 2, "kind": "walk", "length_m": 100, "indoor": True},
    ]
    return Graph.from_records(nodes, edges)


def _building(height):
    # 거리 1(위도 35.1000) 바로 남쪽 5~35 m 에 폭 100 m 건물
    lat0 = 35.1000 - 35 / 110_540
    lat1 = 35.1000 - 5 / 110_540
    return Building(id=1, height_m=height, footprint=[(lat0, 129.0000), (lat0, 129.0011), (lat1, 129.0011), (lat1, 129.0000)])


def test_building_shadow_covers_street_to_the_north():
    g = _street_graph()
    ratios, info = edge_shade_ratios(g, [_building(40.0)], datetime(2026, 8, 3, 13, 0))
    assert info.status == "computed" and info.known_height_count == 1
    assert ratios[0] > 0.9
    assert ratios[1] == 0.0
    assert ratios[2] == 0.0  # 실내


def test_shade_gates():
    g = _street_graph()
    _, night = edge_shade_ratios(g, [_building(40.0)], datetime(2026, 8, 3, 23, 0))
    assert night.status == "not_daylight"
    _, none = edge_shade_ratios(g, [], datetime(2026, 8, 3, 13, 0))
    assert none.status == "no_buildings"
    _, unknown = edge_shade_ratios(g, [_building(None)], datetime(2026, 8, 3, 13, 0))
    assert unknown.status == "no_buildings" and unknown.building_count == 1 and unknown.coverage == 0
    r, disabled = edge_shade_ratios(g, [_building(40.0)], None)
    assert disabled.status == "disabled" and not np.any(r)
