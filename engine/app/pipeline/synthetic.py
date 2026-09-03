"""합성 격자 도시 그래프 생성기 (테스트·개발용).

24×16 격자(50 m 간격)에 언덕, 계단 거리, 비포장 구역, 신호/무신호 횡단보도, 좁은 보도,
지하철 1개 노선(4역, 엘리베이터 상태 다양), 버스 1개 노선, 건물 몇 채를 넣는다.
"""
from __future__ import annotations

import math
from pathlib import Path

from ..graph.geo import haversine_m
from ..graph.model import Graph
from ..graph.store import Building, save_buildings_json

COLS, ROWS = 24, 16
SPACING_M = 50.0
ORIGIN_LAT, ORIGIN_LNG = 35.150, 129.060
SUBWAY_SPEED_MPS = 9.2
SUBWAY_DWELL_S = 30.0
BUS_SPEED_MPS = 5.5
BUS_DWELL_S = 20.0


def _latlng(row: int, col: int, dy_m: float = 0.0, dx_m: float = 0.0) -> tuple[float, float]:
    lat = ORIGIN_LAT + (row * SPACING_M + dy_m) / 110_540.0
    lng = ORIGIN_LNG + (col * SPACING_M + dx_m) / (111_320.0 * math.cos(math.radians(ORIGIN_LAT)))
    return lat, lng


def _elevation(row: int, col: int) -> float:
    x = (col - 12) * SPACING_M
    y = (row - 8) * SPACING_M
    return 40.0 * math.exp(-(x * x + y * y) / (2 * 200.0 ** 2))


def node_id(row: int, col: int) -> int:
    return row * 100 + col


def build_grid_city() -> tuple[Graph, list[Building]]:
    nodes: list[dict] = []
    edges: list[dict] = []
    next_edge = [1]
    next_node = [10_000]

    def add_edge(**kw) -> int:
        eid = next_edge[0]
        next_edge[0] += 1
        edges.append({"id": eid, **kw})
        return eid

    def add_node(**kw) -> int:
        nid = next_node[0]
        next_node[0] += 1
        nodes.append({"id": nid, **kw})
        return nid

    coords: dict[int, tuple[float, float]] = {}
    for r in range(ROWS):
        for c in range(COLS):
            lat, lng = _latlng(r, c)
            nid = node_id(r, c)
            coords[nid] = (lat, lng)
            nodes.append({"id": nid, "kind": "walk", "lat": lat, "lng": lng, "elevation_m": _elevation(r, c)})

    def walk_pair(a: int, b: int, **attrs) -> None:
        (lat1, lng1), (lat2, lng2) = coords[a], coords[b]
        L = float(haversine_m(lat1, lng1, lat2, lng2))
        za = next(n for n in nodes if n["id"] == a)["elevation_m"]
        zb = next(n for n in nodes if n["id"] == b)["elevation_m"]
        grade = (zb - za) / L * 100.0
        base = {"kind": "walk", "mode": "walk", "length_m": L, "grade_pct": grade, "surface": "asphalt", "indoor": False}
        base.update(attrs)
        add_edge(source=a, target=b, **base)
        back = dict(base)
        back["grade_pct"] = -grade
        add_edge(source=b, target=a, **back)

    for r in range(ROWS):
        for c in range(COLS):
            a = node_id(r, c)
            if c + 1 < COLS:
                b = node_id(r, c + 1)
                attrs: dict = {}
                # 계단 거리: 6열-7열 사이, 4~11행 (8행은 경사로 있음)
                if c == 6 and 4 <= r <= 11:
                    attrs.update(stairs=True, step_count=18, ramp=(True if r == 8 else None), handrail=(r % 2 == 0))
                # 주 도로 횡단: 15열-16열
                if c == 15:
                    if r % 2 == 0:
                        attrs.update(crossing="traffic_signals", tactile=(r % 4 == 0))
                    else:
                        attrs.update(crossing="unmarked", kerb=("raised" if r in (5, 9) else "lowered"))
                # 좁은 보도: 20열-21열, 6~9행
                if c == 20 and 6 <= r <= 9:
                    attrs.update(width_m=0.8)
                # 비포장: 13~15행, 0~8열
                if r >= 13 and c < 8:
                    attrs.update(surface="gravel")
                walk_pair(a, b, **attrs)
            if r + 1 < ROWS:
                b = node_id(r + 1, c)
                attrs = {}
                if r >= 13 and c < 8:
                    attrs.update(surface="gravel")
                if 6 <= r <= 8 and c == 20:
                    attrs.update(width_m=0.8)
                walk_pair(a, b, **attrs)

    # ---------- 지하철 ----------
    stations = [("A역", 2, 1, True), ("B역", 2, 9, None), ("C역", 2, 17, False), ("D역", 2, 23, True)]
    platform_ids: list[int] = []
    for name, r, c, elevator in stations:
        grid = node_id(r, c)
        lat, lng = _latlng(r, c, dy_m=8.0, dx_m=6.0)
        entrance = add_node(kind="entrance", lat=lat, lng=lng, name=f"{name} 1번출구", station_id=name)
        platform = add_node(kind="platform", lat=lat, lng=lng, name=name, station_id=name)
        platform_ids.append(platform)
        L = float(haversine_m(coords[grid][0], coords[grid][1], lat, lng))
        for a, b in ((grid, entrance), (entrance, grid)):
            add_edge(source=a, target=b, kind="link", mode="walk", length_m=L, grade_pct=0.0, surface="paved", indoor=False)
        for a, b in ((entrance, platform), (platform, entrance)):
            add_edge(source=a, target=b, kind="vertical", mode="subway", length_m=0.0, elevator=elevator,
                     escalator=(False if elevator is False else None), indoor=True, stop_name=name)
    for direction, order in (("up", range(len(stations))), ("down", range(len(stations) - 1, -1, -1))):
        route_id = f"subway-1-{direction}"
        rs_ids = []
        for i in order:
            name, r, c, _ = stations[i]
            lat, lng = _latlng(r, c, dy_m=8.0, dx_m=6.0)
            rs = add_node(kind="route_stop", lat=lat, lng=lng, name=name, station_id=name)
            rs_ids.append(rs)
            add_edge(source=platform_ids[i], target=rs, kind="board", mode="subway", length_m=0.0, route_id=route_id,
                     route_name="1호선", headway_s=360.0, indoor=True, stop_name=name)
            add_edge(source=rs, target=platform_ids[i], kind="alight", mode="subway", length_m=0.0, route_id=route_id,
                     route_name="1호선", indoor=True, stop_name=name)
        for a, b in zip(rs_ids, rs_ids[1:]):
            na = next(n for n in nodes if n["id"] == a)
            nb = next(n for n in nodes if n["id"] == b)
            L = float(haversine_m(na["lat"], na["lng"], nb["lat"], nb["lng"]))
            add_edge(source=a, target=b, kind="ride", mode="subway", length_m=L, time_s=L / SUBWAY_SPEED_MPS + SUBWAY_DWELL_S,
                     route_id=route_id, route_name="1호선", indoor=True)

    # ---------- 버스 ----------
    bus_row = 14
    stop_cols = list(range(0, COLS, 4))
    stop_ids: list[int] = []
    for c in stop_cols:
        grid = node_id(bus_row, c)
        lat, lng = _latlng(bus_row, c, dy_m=-6.0)
        stop = add_node(kind="stop", lat=lat, lng=lng, name=f"정류장{c}", station_id=f"bus-stop-{c}")
        stop_ids.append(stop)
        L = float(haversine_m(coords[grid][0], coords[grid][1], lat, lng))
        for a, b in ((grid, stop), (stop, grid)):
            add_edge(source=a, target=b, kind="link", mode="walk", length_m=L, grade_pct=0.0, surface="paved", indoor=False)
    for direction, order in (("east", range(len(stop_cols))), ("west", range(len(stop_cols) - 1, -1, -1))):
        route_id = f"bus-77-{direction}"
        rs_ids = []
        for i in order:
            c = stop_cols[i]
            lat, lng = _latlng(bus_row, c, dy_m=-6.0)
            rs = add_node(kind="route_stop", lat=lat, lng=lng, name=f"정류장{c}", station_id=f"bus-stop-{c}")
            rs_ids.append(rs)
            add_edge(source=stop_ids[i], target=rs, kind="board", mode="bus", length_m=0.0, route_id=route_id, route_name="77번",
                     headway_s=600.0, low_floor_ratio=0.5, indoor=False, stop_name=f"정류장{c}")
            add_edge(source=rs, target=stop_ids[i], kind="alight", mode="bus", length_m=0.0, route_id=route_id, route_name="77번",
                     indoor=False, stop_name=f"정류장{c}")
        for a, b in zip(rs_ids, rs_ids[1:]):
            na = next(n for n in nodes if n["id"] == a)
            nb = next(n for n in nodes if n["id"] == b)
            L = float(haversine_m(na["lat"], na["lng"], nb["lat"], nb["lng"]))
            add_edge(source=a, target=b, kind="ride", mode="bus", length_m=L, time_s=L / BUS_SPEED_MPS + BUS_DWELL_S,
                     route_id=route_id, route_name="77번", indoor=True)

    # ---------- 건물 ----------
    buildings: list[Building] = []
    bid = 1
    # 남쪽(낮은 행) 블록에 높은 건물: 9~11행, 3열~13열 사이 블록 남쪽 절반
    for r in (9, 10):
        for c in range(3, 13, 2):
            p1 = _latlng(r, c, dy_m=10.0, dx_m=10.0)
            p2 = _latlng(r, c, dy_m=10.0, dx_m=40.0)
            p3 = _latlng(r, c, dy_m=40.0, dx_m=40.0)
            p4 = _latlng(r, c, dy_m=40.0, dx_m=10.0)
            buildings.append(Building(id=bid, height_m=(45.0 if c % 4 == 1 else 18.0), footprint=[p1, p2, p3, p4]))
            bid += 1
    # 그늘 대로: 12행 거리 남쪽(11행 블록)에 2~21열까지 이어지는 60 m 건물
    for c in range(2, 22):
        p1 = _latlng(11, c, dy_m=15.0, dx_m=0.0)
        p2 = _latlng(11, c, dy_m=15.0, dx_m=50.0)
        p3 = _latlng(11, c, dy_m=45.0, dx_m=50.0)
        p4 = _latlng(11, c, dy_m=45.0, dx_m=0.0)
        buildings.append(Building(id=bid, height_m=60.0, footprint=[p1, p2, p3, p4]))
        bid += 1
    # 높이를 모르는 건물 하나
    p = [_latlng(4, 18, dy_m=10, dx_m=10), _latlng(4, 18, dy_m=10, dx_m=40), _latlng(4, 18, dy_m=40, dx_m=40), _latlng(4, 18, dy_m=40, dx_m=10)]
    buildings.append(Building(id=bid, height_m=None, footprint=p))

    graph = Graph.from_records(nodes, edges)
    return graph, buildings


def write_sample(out_dir: str | Path) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    graph, buildings = build_grid_city()
    graph_path = out / "grid_city.npz"
    buildings_path = out / "grid_city_buildings.json"
    graph.save_npz(graph_path)
    save_buildings_json(buildings_path, buildings)
    return graph_path, buildings_path


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "data/samples"
    g, b = write_sample(target)
    print(f"wrote {g} and {b}")
