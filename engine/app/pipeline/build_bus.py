"""부산 버스 그래프 빌더.

정류장 좌표: data/bus/busan_bus_stops_national_20251031.csv (국토부 전국 버스정류장 표준데이터, 부산 9,975개)
노선-정류장 순서: 두 가지 입력 중 하나
  1) GTFS 폴더 (routes.txt, trips.txt, stop_times.txt, stops.txt)
  2) BIMS 캐시 폴더 (bims_fetch.py 가 저장한 routes.json / route_<lineid>.json)
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from ..graph.model import Graph
from .transit import BUS_NODE_BASE, TransitRoute, TransitSpec, TransitStop, build_transit_graph

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "bus"
DEFAULT_STOPS_CSV = DATA_DIR / "busan_bus_stops_national_20251031.csv"
BUS_SPEED_MPS = 5.5
BUS_DWELL_S = 20.0
DEFAULT_HEADWAY_S = 720.0
BUSAN_BBOX = (34.8, 128.7, 35.5, 129.4)


@dataclass
class BusReport:
    routes: int
    stops: int
    stops_without_coordinates: int
    source: str


def load_stops_csv(path: Path = DEFAULT_STOPS_CSV) -> dict[str, TransitStop]:
    """stop_id / ars_no 양쪽 키로 조회 가능한 정류장 사전."""
    out: dict[str, TransitStop] = {}
    if not Path(path).is_file():
        return out
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                lat, lng = float(r["lat"]), float(r["lng"])
            except (KeyError, ValueError):
                continue
            if not (BUSAN_BBOX[0] <= lat <= BUSAN_BBOX[2] and BUSAN_BBOX[1] <= lng <= BUSAN_BBOX[3]):
                continue
            stop = TransitStop(id=f"bus:{r['stop_id']}", name=r.get("name", ""), lat=lat, lng=lng)
            out[r["stop_id"]] = stop
            ars = str(r.get("ars_no", "")).strip()
            if ars:
                out.setdefault(f"ars:{ars}", stop)
    return out


def _hms_to_s(value: str) -> float | None:
    try:
        h, m, s = value.strip().split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except (ValueError, AttributeError):
        return None


def load_gtfs(gtfs_dir: Path, stops_csv: dict[str, TransitStop] | None = None) -> TransitSpec:
    """GTFS → TransitSpec. (route_id, direction_id)별 정류장이 가장 많은 trip을 대표로 삼는다."""
    gtfs_dir = Path(gtfs_dir)

    def read(name: str) -> list[dict]:
        p = gtfs_dir / name
        if not p.is_file():
            return []
        with open(p, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    routes = {r["route_id"]: r for r in read("routes.txt")}
    stops = {}
    for r in read("stops.txt"):
        try:
            stops[r["stop_id"]] = TransitStop(id=f"bus:{r['stop_id']}", name=r.get("stop_name", ""), lat=float(r["stop_lat"]), lng=float(r["stop_lon"]))
        except (KeyError, ValueError):
            continue
    if stops_csv:
        for k, v in stops_csv.items():
            stops.setdefault(k, v)
    trips = {t["trip_id"]: t for t in read("trips.txt")}
    times: dict[str, list[dict]] = defaultdict(list)
    for st in read("stop_times.txt"):
        times[st["trip_id"]].append(st)
    # 대표 trip 선택
    best: dict[tuple[str, str], tuple[int, str]] = {}
    first_departures: dict[tuple[str, str], list[float]] = defaultdict(list)
    for trip_id, rows in times.items():
        t = trips.get(trip_id)
        if not t:
            continue
        key = (t["route_id"], t.get("direction_id", "0") or "0")
        rows.sort(key=lambda r: int(r["stop_sequence"]))
        if key not in best or len(rows) > best[key][0]:
            best[key] = (len(rows), trip_id)
        dep = _hms_to_s(rows[0].get("departure_time") or rows[0].get("arrival_time") or "")
        if dep is not None:
            first_departures[key].append(dep)
    out: list[TransitRoute] = []
    for (route_id, direction), (_, trip_id) in best.items():
        rows = times[trip_id]
        seq: list[TransitStop] = []
        travel: list[float | None] = []
        prev_t: float | None = None
        for r in rows:
            s = stops.get(r["stop_id"])
            if s is None:
                continue
            arr = _hms_to_s(r.get("arrival_time") or "")
            if seq:
                travel.append((arr - prev_t) if (arr is not None and prev_t is not None and arr > prev_t) else None)
            seq.append(s)
            prev_t = arr if arr is not None else prev_t
        if len(seq) < 2:
            continue
        deps = sorted(first_departures.get((route_id, direction), []))
        headway = None
        if len(deps) >= 2:
            gaps = [b - a for a, b in zip(deps, deps[1:]) if b > a]
            headway = (sum(gaps) / len(gaps)) if gaps else None
        route = routes.get(route_id, {})
        name = route.get("route_short_name") or route.get("route_long_name") or route_id
        lfr = route.get("low_floor_ratio")
        out.append(TransitRoute(id=f"bus-{route_id}-{direction}", name=name, mode="bus", stops=seq, headway_s=headway or DEFAULT_HEADWAY_S,
                                low_floor_ratio=(float(lfr) if lfr not in (None, "") else None), travel_s=travel,
                                color=route.get("route_color", "")))
    return TransitSpec(routes=out, mode="bus", stop_kind="stop", speed_mps=BUS_SPEED_MPS, dwell_s=BUS_DWELL_S)


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_bims_cache(cache_dir: Path, stops_csv: dict[str, TransitStop] | None = None) -> tuple[TransitSpec, int]:
    """bims_fetch.py 캐시 → TransitSpec. 반환: (spec, 좌표 없는 정류장 수)."""
    cache_dir = Path(cache_dir)
    routes_meta = json.loads((cache_dir / "routes.json").read_text(encoding="utf-8")) if (cache_dir / "routes.json").is_file() else {}
    stops_csv = stops_csv or {}
    out: list[TransitRoute] = []
    missing = 0
    for path in sorted(cache_dir.glob("route_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        line_id = str(payload.get("lineid") or path.stem.replace("route_", ""))
        rows = payload.get("stops") or []
        meta = routes_meta.get(line_id, {})
        name = str(meta.get("lineno") or meta.get("buslinenum") or (rows[0].get("lineno") if rows else "") or line_id)
        headway = _num(meta.get("headway")) or _num(meta.get("headway_s"))
        headway_s = headway * 60.0 if headway and headway < 100 else headway
        lfr = _num(meta.get("low_floor_ratio"))
        by_dir: dict[str, list[tuple[int, TransitStop]]] = defaultdict(list)
        for r in rows:
            idx = int(_num(r.get("bstopidx")) or 0)
            direction = str(r.get("direction") or r.get("updown") or "0")
            lat, lng = _num(r.get("lat")), _num(r.get("lin") or r.get("lng"))
            stop = None
            nodeid = str(r.get("nodeid") or r.get("bstopid") or "").strip()
            ars = str(r.get("arsno") or "").strip()
            if lat is not None and lng is not None:
                stop = TransitStop(id=f"bus:{nodeid or ars or idx}", name=str(r.get("bstopnm") or r.get("nodenm") or ""), lat=lat, lng=lng)
            elif nodeid and nodeid in stops_csv:
                stop = stops_csv[nodeid]
            elif ars and f"ars:{ars}" in stops_csv:
                stop = stops_csv[f"ars:{ars}"]
            if stop is None:
                missing += 1
                continue
            by_dir[direction].append((idx, stop))
        for direction, items in by_dir.items():
            items.sort(key=lambda x: x[0])
            seq = [s for _, s in items]
            if len(seq) < 2:
                continue
            out.append(TransitRoute(id=f"bus-{line_id}-{direction}", name=name, mode="bus", stops=seq,
                                    headway_s=headway_s or DEFAULT_HEADWAY_S, low_floor_ratio=lfr))
    return TransitSpec(routes=out, mode="bus", stop_kind="stop", speed_mps=BUS_SPEED_MPS, dwell_s=BUS_DWELL_S), missing


def build_bus_graph(spec: TransitSpec) -> Graph:
    return build_transit_graph(spec, BUS_NODE_BASE).graph


def build_from_sources(gtfs_dir: Path | None, bims_dir: Path | None, stops_csv: Path = DEFAULT_STOPS_CSV) -> tuple[Graph, BusReport]:
    stops = load_stops_csv(stops_csv)
    if gtfs_dir:
        spec = load_gtfs(gtfs_dir, stops)
        missing, source = 0, f"gtfs:{gtfs_dir}"
    elif bims_dir:
        spec, missing = load_bims_cache(bims_dir, stops)
        source = f"bims:{bims_dir}"
    else:
        raise ValueError("GTFS 폴더 또는 BIMS 캐시 폴더가 필요합니다.")
    graph = build_bus_graph(spec)
    return graph, BusReport(routes=len(spec.routes), stops=len(spec.unique_stops()), stops_without_coordinates=missing, source=source)
