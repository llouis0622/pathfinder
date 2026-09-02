import json

import numpy as np
import pytest

from app.graph.model import TRI_FALSE, TRI_TRUE, TRI_UNKNOWN
from app.pipeline.build_bus import build_bus_graph, load_bims_cache, load_gtfs, load_stops_csv
from app.pipeline.build_subway import build_subway_graph, station_key
from app.pipeline.transit import TransitRoute, TransitSpec, TransitStop, build_transit_graph


def test_station_key():
    assert station_key("서면역(1호선)") == "서면"
    assert station_key("다대포해수욕장") == "다대포해수욕장"
    assert station_key("부산대역") == "부산대"
    assert station_key("수영역(3호선)") == "수영"


def test_build_transit_graph_basic():
    stops = [TransitStop("s1", "A", 35.10, 129.00), TransitStop("s2", "B", 35.10, 129.01), TransitStop("s3", "C", 35.10, 129.02)]
    spec = TransitSpec(routes=[TransitRoute("r-0", "10", "bus", stops, headway_s=600, low_floor_ratio=0.4, travel_s=[120, None])],
                       mode="bus", stop_kind="stop", speed_mps=5.5, dwell_s=20)
    build = build_transit_graph(spec, 1000)
    g = build.graph
    assert build.stops == 3 and build.routes == 1
    assert (g.nodes["kind"] == "stop").sum() == 3 and (g.nodes["kind"] == "route_stop").sum() == 3
    kinds = g.edges["kind"]
    assert (kinds == "board").sum() == 3 and (kinds == "alight").sum() == 3 and (kinds == "ride").sum() == 2
    rides = np.nonzero(kinds == "ride")[0]
    assert g.edges["time_s"][rides[0]] == pytest.approx(120)
    assert g.edges["time_s"][rides[1]] > 100     # 거리/속도 + 정차
    board = np.nonzero(kinds == "board")[0][0]
    assert g.edges["headway_s"][board] == 600 and g.edges["low_floor_ratio"][board] == pytest.approx(0.4)
    assert g.edges["indoor"][board] == TRI_FALSE


def test_subway_builder_real_data():
    g, rep = build_subway_graph()
    assert rep.lines == 4 and rep.stations == 108 and rep.platforms == 114
    assert rep.transfers >= 5                       # 서면·연산·수영·덕천·미남·동래
    assert rep.entrances_verified >= 50
    kinds = g.edges["kind"]
    assert (kinds == "ride").sum() == 2 * (114 - 4)  # 양방향 × (역 수 − 노선 수)
    v = np.nonzero(kinds == "vertical")[0]
    elev = g.edges["elevator"][v]
    assert (elev == TRI_TRUE).sum() >= 100 and (elev == TRI_UNKNOWN).sum() > 0
    names = set(g.nodes["name"].tolist())
    assert "서면역" in names and "구서역 3번출구" in names
    # 모든 엣지가 노드를 참조하고 route_stop 이 승강장과 연결된다
    assert g.num_edges > 0 and len(g.id_to_index) == g.num_nodes


def _write_gtfs(d):
    (d / "routes.txt").write_text("route_id,route_short_name,route_type,low_floor_ratio\n77,77번,3,0.5\n", encoding="utf-8")
    (d / "trips.txt").write_text("route_id,service_id,trip_id,direction_id\n77,wd,t1,0\n77,wd,t2,0\n77,wd,t3,1\n", encoding="utf-8")
    (d / "stops.txt").write_text("stop_id,stop_name,stop_lat,stop_lon\nA,정류장A,35.10,129.00\nB,정류장B,35.10,129.01\nC,정류장C,35.10,129.02\n", encoding="utf-8")
    (d / "stop_times.txt").write_text(
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "t1,08:00:00,08:00:00,A,1\nt1,08:03:00,08:03:00,B,2\nt1,08:07:00,08:07:00,C,3\n"
        "t2,08:12:00,08:12:00,A,1\nt2,08:15:00,08:15:00,B,2\nt2,08:19:00,08:19:00,C,3\n"
        "t3,09:00:00,09:00:00,C,1\nt3,09:04:00,09:04:00,B,2\nt3,09:07:00,09:07:00,A,3\n", encoding="utf-8")


def test_gtfs_loader(tmp_path):
    _write_gtfs(tmp_path)
    spec = load_gtfs(tmp_path)
    assert len(spec.routes) == 2
    r0 = next(r for r in spec.routes if r.id == "bus-77-0")
    assert [s.name for s in r0.stops] == ["정류장A", "정류장B", "정류장C"]
    assert r0.travel_s == [180, 240]
    assert r0.headway_s == pytest.approx(720)
    assert r0.low_floor_ratio == 0.5
    g = build_bus_graph(spec)
    assert (g.nodes["kind"] == "stop").sum() == 3
    assert (g.edges["kind"] == "ride").sum() == 4


def test_bims_cache_loader(tmp_path):
    (tmp_path / "routes.json").write_text(json.dumps({"5001": {"lineid": "5001", "lineno": "1001", "headway": 12}}), encoding="utf-8")
    rows = [
        {"bstopidx": "1", "nodeid": "BSB1", "arsno": "12001", "bstopnm": "A", "lat": "35.10", "lin": "129.00", "direction": "0"},
        {"bstopidx": "2", "nodeid": "BSB2", "arsno": "12002", "bstopnm": "B", "lat": "35.10", "lin": "129.01", "direction": "0"},
        {"bstopidx": "3", "nodeid": "BSB3", "arsno": "12003", "bstopnm": "C", "direction": "0"},              # 좌표 없음 → CSV 보완
        {"bstopidx": "4", "nodeid": "NOPE", "arsno": "99999", "bstopnm": "D", "direction": "0"},              # 보완 불가
        {"bstopidx": "1", "nodeid": "BSB3", "arsno": "12003", "bstopnm": "C", "lat": "35.10", "lin": "129.02", "direction": "1"},
        {"bstopidx": "2", "nodeid": "BSB1", "arsno": "12001", "bstopnm": "A", "lat": "35.10", "lin": "129.00", "direction": "1"},
    ]
    (tmp_path / "route_5001.json").write_text(json.dumps({"lineid": "5001", "stops": rows}), encoding="utf-8")
    csv_stops = {"BSB3": TransitStop("bus:BSB3", "C", 35.10, 129.02)}
    spec, missing = load_bims_cache(tmp_path, csv_stops)
    assert missing == 1
    assert {r.id for r in spec.routes} == {"bus-5001-0", "bus-5001-1"}
    r0 = next(r for r in spec.routes if r.id == "bus-5001-0")
    assert [s.name for s in r0.stops] == ["A", "B", "C"] and r0.name == "1001" and r0.headway_s == 720


def test_stops_csv_loads_busan():
    stops = load_stops_csv()
    assert len(stops) > 9000
    s = next(iter(stops.values()))
    assert 34.8 <= s.lat <= 35.5 and 128.7 <= s.lng <= 129.4
