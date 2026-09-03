"""부산 도시철도 그래프 빌더.

입력 (data/subway/):
- busan_subway_lines.json                          노선별 역 순서·좌표·배차
- busan_subway_stations.csv                        역별 엘리베이터 유무(O/N)
- busan_subway_accessible_exit_coordinates_*.csv   엘리베이터 경로가 확인된 출입구 좌표
- busan_subway_elevator_routes_*.csv               역·출입구별 엘리베이터 이동경로

노드: platform(노선·역), entrance(출입구), route_stop
엣지: entrance↔platform vertical(엘리베이터 True/None/False), platform↔platform vertical(환승),
      board/alight/ride (transit.build_transit_graph)
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..graph.model import Graph
from .transit import SUBWAY_NODE_BASE, TransitRoute, TransitSpec, TransitStop, build_transit_graph

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "subway"
TRANSFER_TIME_S = 240.0


def station_key(name: str) -> str:
    """'서면역(1호선)' → '서면', '다대포해수욕장' → '다대포해수욕장'."""
    s = name.strip()
    s = re.sub(r"\(.*?\)", "", s)
    s = s.strip()
    if s.endswith("역") and len(s) > 1:
        s = s[:-1]
    return s


@dataclass
class SubwayInputs:
    lines_json: Path = DATA_DIR / "busan_subway_lines.json"
    stations_csv: Path = DATA_DIR / "busan_subway_stations.csv"
    exits_csv: Path = DATA_DIR / "busan_subway_accessible_exit_coordinates_20260813.csv"
    elevator_routes_csv: Path = DATA_DIR / "busan_subway_elevator_routes_20251231.csv"


@dataclass
class SubwayReport:
    lines: int
    stations: int
    platforms: int
    entrances: int
    entrances_verified: int
    transfers: int


def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_subway_graph(inputs: SubwayInputs | None = None) -> tuple[Graph, SubwayReport]:
    inputs = inputs or SubwayInputs()
    lines = json.loads(Path(inputs.lines_json).read_text(encoding="utf-8"))
    station_rows = _read_csv(inputs.stations_csv) if Path(inputs.stations_csv).is_file() else []
    exit_rows = _read_csv(inputs.exits_csv) if Path(inputs.exits_csv).is_file() else []
    elev_rows = _read_csv(inputs.elevator_routes_csv) if Path(inputs.elevator_routes_csv).is_file() else []

    station_elevator: dict[str, bool] = {}
    for r in station_rows:
        station_elevator[station_key(r["name"])] = str(r.get("elevator", "")).strip().upper() == "O"
    elevator_exits: set[tuple[str, str, str]] = set()   # (line, station, exit_no)
    elevator_stations: set[tuple[str, str]] = set()
    for r in elev_rows:
        line = str(r.get("호선", "")).strip()
        st = station_key(str(r.get("역명", "")))
        for exit_no in str(r.get("출입구번호", "")).replace("，", ",").split(","):
            exit_no = exit_no.strip()
            if exit_no:
                elevator_exits.add((line, st, exit_no))
        elevator_stations.add((line, st))
    exits_by_station: dict[tuple[str, str], list[dict]] = {}
    for r in exit_rows:
        key = (str(r["station_line"]).strip(), station_key(str(r["station_name"])))
        exits_by_station.setdefault(key, []).append(r)

    speed = float(lines.get("speed_mps", 9.2))
    dwell = float(lines.get("dwell_s", 30.0))
    routes: list[TransitRoute] = []
    platform_stops: dict[str, TransitStop] = {}
    line_of_stop: dict[str, str] = {}
    for line in lines["lines"]:
        line_no = str(line["id"]).split("-")[-1]
        stops: list[TransitStop] = []
        for st in line["stations"]:
            key = station_key(st["name"])
            sid = f"subway:{line_no}:{key}"
            stop = TransitStop(id=sid, name=f"{key}역", lat=float(st["lat"]), lng=float(st["lng"]))
            platform_stops[sid] = stop
            line_of_stop[sid] = line_no
            stops.append(stop)
        for direction, seq in (("up", stops), ("down", list(reversed(stops)))):
            routes.append(TransitRoute(id=f"{line['id']}-{direction}", name=line["name"], mode="subway", stops=seq,
                                       headway_s=float(line.get("headway_s", 420)), color=line.get("color", "")))
    spec = TransitSpec(routes=routes, mode="subway", stop_kind="platform", speed_mps=speed, dwell_s=dwell)
    build = build_transit_graph(spec, SUBWAY_NODE_BASE)
    graph = build.graph
    next_node = build.next_node_id
    next_edge = int(graph.edges["id"].max()) + 1 if graph.num_edges else 1

    nodes: list[dict] = []
    edges: list[dict] = []
    entrances = verified = transfers = 0

    def vertical(a: int, b: int, elevator: bool | None, name: str) -> None:
        nonlocal next_edge
        for s, t in ((a, b), (b, a)):
            edges.append({"id": next_edge, "source": s, "target": t, "kind": "vertical", "mode": "subway", "length_m": 0.0,
                          "elevator": elevator, "escalator": (None if elevator is not False else None), "indoor": True, "stop_name": name})
            next_edge += 1

    # 출입구
    for sid, stop in platform_stops.items():
        line_no = line_of_stop[sid]
        key = station_key(stop.name)
        platform_id = build.stop_node_ids[sid]
        has_elev = station_elevator.get(key, False) or (line_no, key) in elevator_stations
        for r in exits_by_station.get((line_no, key), []):
            exit_no = str(r["exit_no"]).strip()
            ent = next_node
            next_node += 1
            nodes.append({"id": ent, "kind": "entrance", "lat": float(r["lat"]), "lng": float(r["lng"]),
                          "name": f"{key}역 {exit_no}번출구", "station_id": sid})
            is_verified = (line_no, key, exit_no) in elevator_exits
            vertical(ent, platform_id, True if is_verified else (None if has_elev else False), stop.name)
            entrances += 1
            verified += int(is_verified)
        # 역 중심 출입구 (위치 미상 출입구 대표)
        ent = next_node
        next_node += 1
        nodes.append({"id": ent, "kind": "entrance", "lat": stop.lat, "lng": stop.lng, "name": f"{key}역 출입구", "station_id": sid})
        vertical(ent, platform_id, None if has_elev else False, stop.name)
        entrances += 1

    # 환승: 같은 역 이름의 다른 노선 승강장
    by_key: dict[str, list[str]] = {}
    for sid in platform_stops:
        by_key.setdefault(station_key(platform_stops[sid].name), []).append(sid)
    for key, sids in by_key.items():
        for i in range(len(sids)):
            for j in range(i + 1, len(sids)):
                a, b = build.stop_node_ids[sids[i]], build.stop_node_ids[sids[j]]
                elev = station_elevator.get(key)
                for s, t in ((a, b), (b, a)):
                    edges.append({"id": next_edge, "source": s, "target": t, "kind": "vertical", "mode": "subway", "length_m": 0.0,
                                  "time_s": TRANSFER_TIME_S, "elevator": elev, "indoor": True, "stop_name": f"{key}역 환승"})
                    next_edge += 1
                transfers += 1

    extra_nodes, extra_edges = Graph.arrays_from_records(nodes, edges)
    all_nodes = {k: np.concatenate([graph.nodes[k], extra_nodes[k]]) for k in graph.nodes}
    all_edges = {k: np.concatenate([graph.edges[k], extra_edges[k]]) for k in graph.edges}
    result = Graph(all_nodes, all_edges)
    report = SubwayReport(lines=len(lines["lines"]), stations=len(by_key), platforms=len(platform_stops),
                          entrances=entrances, entrances_verified=verified, transfers=transfers)
    return result, report


if __name__ == "__main__":
    import sys

    g, rep = build_subway_graph()
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "../data/build/subway.npz")
    out.parent.mkdir(parents=True, exist_ok=True)
    g.save_npz(out)
    print(rep, "->", out)
