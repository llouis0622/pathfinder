"""엣지 열 → 구간(leg)·특성·배지·주의사항."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..cost.model import CostResult
from ..cost.profiles import ProfileParams
from ..cost.weather import WeatherContext
from ..graph.model import TRI_TRUE, TRI_UNKNOWN, Graph
from .schemas import LegOut, RouteFeaturesOut, RouteOut, SlopeSegment

ROUGH_SURFACES = {"cobblestone", "sett", "unhewn_cobblestone", "gravel", "fine_gravel", "compacted",
                  "pebblestone", "unpaved", "dirt", "ground", "grass", "sand", "earth", "mud"}
STEEP_CAUTION_PCT = 8.0
UNSHADED_CAUTION_M = 500.0
LOW_FLOOR_CAUTION_RATIO = 0.3


@dataclass
class _WalkAcc:
    path: list[list[float]] = field(default_factory=list)
    distance: float = 0.0
    duration: float = 0.0
    uphill: float = 0.0
    downhill: float = 0.0
    max_grade: float | None = None
    stairs: int = 0
    steps: int = 0
    shaded_len: float = 0.0
    shade_len: float = 0.0
    crossings: int = 0
    rough: float = 0.0
    segments: list[SlopeSegment] = field(default_factory=list)


def _append_path(path: list[list[float]], pts: list[tuple[float, float]]) -> None:
    for p in pts:
        pt = [round(p[0], 7), round(p[1], 7)]
        if not path or path[-1] != pt:
            path.append(pt)


def _finish_walk(acc: _WalkAcc, legs: list[LegOut]) -> None:
    if acc.distance <= 0 and not acc.segments:
        return
    legs.append(LegOut(
        kind="walk", mode="walk", path=acc.path, distance_m=round(acc.distance, 1), duration_s=round(acc.duration, 1),
        uphill_m=round(acc.uphill, 1), downhill_m=round(acc.downhill, 1),
        max_grade_pct=(None if acc.max_grade is None else round(acc.max_grade, 1)),
        stairs_count=acc.stairs, step_count=acc.steps,
        shade_ratio=(round(acc.shaded_len / acc.shade_len, 3) if acc.shade_len > 0 else None),
        unshaded_m=round(max(acc.shade_len - acc.shaded_len, 0.0), 1),
        crossings=acc.crossings, segments=acc.segments,
    ))


def build_route(
    graph: Graph, edge_path: list[int], cost: CostResult, shade_ratio: np.ndarray,
    generalized_cost: float, origin_algorithm: str, rank: int, route_id: str,
) -> RouteOut:
    e = graph.edges
    n = graph.nodes
    legs: list[LegOut] = []
    walk = _WalkAcc()
    ride: dict | None = None
    full_path: list[list[float]] = []
    total_time = walk_time = ride_time = wait_time = 0.0
    boardings = 0
    elevator_count = unverified = 0
    modes: list[str] = []

    for idx in edge_path:
        kind = str(e["kind"][idx])
        t = float(cost.time_s[idx])
        total_time += t
        pts = graph.edge_geometry(idx)
        _append_path(full_path, pts)
        if kind in ("walk", "link", "transfer"):
            if "walk" not in modes:
                modes.append("walk")
            L = float(e["length_m"][idx])
            g = e["grade_pct"][idx]
            g_val = None if np.isnan(g) else float(g)
            _append_path(walk.path, pts)
            walk.distance += L
            walk.duration += t
            walk_time += t
            if g_val is not None:
                dz = g_val / 100.0 * L
                if dz > 0:
                    walk.uphill += dz
                else:
                    walk.downhill -= dz
                if walk.max_grade is None or abs(g_val) > walk.max_grade:
                    walk.max_grade = abs(g_val)
            is_stairs = e["stairs"][idx] == TRI_TRUE
            if is_stairs:
                walk.stairs += 1
                sc = e["step_count"][idx]
                walk.steps += int(sc) if not np.isnan(sc) else 12
            if e["indoor"][idx] != TRI_TRUE:
                walk.shade_len += L
                walk.shaded_len += L * float(shade_ratio[idx])
            crossing = str(e["crossing"][idx])
            if crossing:
                walk.crossings += 1
            surface = str(e["surface"][idx])
            if surface in ROUGH_SURFACES:
                walk.rough += L
            walk.segments.append(SlopeSegment(
                path=[[round(p[0], 7), round(p[1], 7)] for p in pts], grade_pct=(None if g_val is None else round(g_val, 1)),
                distance_m=round(L, 1), shade_ratio=round(float(shade_ratio[idx]), 3), stairs=bool(is_stairs),
                surface=surface, crossing=crossing,
            ))
        elif kind == "board":
            _finish_walk(walk, legs)
            walk = _WalkAcc()
            boardings += 1
            wait_time += t
            mode = str(e["mode"][idx]) or "transit"
            if mode not in modes:
                modes.append(mode)
            lfr = e["low_floor_ratio"][idx]
            ride = {
                "mode": mode, "route_id": str(e["route_id"][idx]), "route_name": str(e["route_name"][idx]),
                "from_name": str(e["stop_name"][idx]) or str(n["name"][graph.src[idx]]), "to_name": "",
                "wait": t, "duration": 0.0, "distance": 0.0, "stops": 0, "path": [],
                "low_floor_ratio": (None if np.isnan(lfr) else float(lfr)),
            }
            _append_path(ride["path"], pts[-1:])
        elif kind == "ride":
            if ride is None:
                ride = {"mode": str(e["mode"][idx]) or "transit", "route_id": str(e["route_id"][idx]), "route_name": str(e["route_name"][idx]),
                        "from_name": str(n["name"][graph.src[idx]]), "to_name": "", "wait": 0.0, "duration": 0.0,
                        "distance": 0.0, "stops": 0, "path": [], "low_floor_ratio": None}
            ride["duration"] += t
            ride["distance"] += float(e["length_m"][idx])
            ride["stops"] += 1
            ride_time += t
            _append_path(ride["path"], pts)
        elif kind == "alight":
            total_time_alight = t
            walk_time += 0.0
            if ride is not None:
                ride["to_name"] = str(e["stop_name"][idx]) or str(n["name"][graph.dst[idx]])
                ride["duration"] += total_time_alight
                legs.append(LegOut(
                    kind="ride", mode=ride["mode"], path=ride["path"], distance_m=round(ride["distance"], 1),
                    duration_s=round(ride["duration"], 1), wait_s=round(ride["wait"], 1), route_id=ride["route_id"],
                    route_name=ride["route_name"], from_name=ride["from_name"], to_name=ride["to_name"],
                    stop_count=ride["stops"], low_floor_ratio=ride["low_floor_ratio"],
                ))
                ride = None
        elif kind == "vertical":
            _finish_walk(walk, legs)
            walk = _WalkAcc()
            elev = int(e["elevator"][idx])
            esc = int(e["escalator"][idx])
            if elev == TRI_TRUE:
                facility, verified = "elevator", True
                elevator_count += 1
            elif elev == TRI_UNKNOWN:
                facility, verified = "unknown", None
                unverified += 1
            elif esc == TRI_TRUE:
                facility, verified = "escalator", True
            else:
                facility, verified = "stairs", True
            station = str(n["name"][graph.dst[idx]]) or str(n["name"][graph.src[idx]])
            legs.append(LegOut(kind="vertical", mode="subway", path=[[round(p[0], 7), round(p[1], 7)] for p in pts],
                               distance_m=0.0, duration_s=round(t, 1), facility=facility, station_name=station, verified=verified))
    _finish_walk(walk, legs)
    if ride is not None:  # 하차 없이 끝난 경우(비정상)는 그대로 닫는다
        legs.append(LegOut(kind="ride", mode=ride["mode"], path=ride["path"], distance_m=round(ride["distance"], 1),
                           duration_s=round(ride["duration"], 1), wait_s=round(ride["wait"], 1), route_id=ride["route_id"],
                           route_name=ride["route_name"], from_name=ride["from_name"], to_name=ride["to_name"], stop_count=ride["stops"]))

    walk_legs = [leg for leg in legs if leg.kind == "walk"]
    walk_distance = sum(leg.distance_m for leg in walk_legs)
    grades = [leg.max_grade_pct for leg in walk_legs if leg.max_grade_pct is not None]
    shade_len = sum(leg.distance_m for leg in walk_legs if leg.shade_ratio is not None)
    shaded = sum(leg.distance_m * leg.shade_ratio for leg in walk_legs if leg.shade_ratio is not None)
    idx = np.asarray(edge_path, dtype=np.int64)
    walk_mask = np.isin(e["kind"][idx], ["walk", "link", "transfer"]) if idx.size else np.zeros(0, bool)
    walk_idx = idx[walk_mask]
    g_abs = np.abs(np.nan_to_num(e["grade_pct"][walk_idx].astype(float), nan=0.0))
    lens = e["length_m"][walk_idx].astype(float)
    known = ~np.isnan(e["grade_pct"][walk_idx].astype(float))
    avg_grade = float(np.average(g_abs[known], weights=lens[known])) if known.any() and lens[known].sum() > 0 else None

    features = RouteFeaturesOut(
        total_duration_s=round(total_time, 1), walk_distance_m=round(walk_distance, 1), walk_duration_s=round(walk_time, 1),
        ride_duration_s=round(ride_time, 1), wait_duration_s=round(wait_time, 1), boardings=boardings,
        transfers=max(0, boardings - 1), max_grade_pct=(max(grades) if grades else None),
        avg_grade_pct=(None if avg_grade is None else round(avg_grade, 2)),
        uphill_m=round(sum(leg.uphill_m for leg in walk_legs), 1), downhill_m=round(sum(leg.downhill_m for leg in walk_legs), 1),
        stairs_count=sum(leg.stairs_count for leg in walk_legs), total_steps=sum(leg.step_count for leg in walk_legs),
        elevator_count=elevator_count, unverified_vertical_count=unverified,
        shade_ratio=(round(shaded / shade_len, 3) if shade_len > 0 else None),
        unshaded_walk_m=round(max(shade_len - shaded, 0.0), 1), crossings=sum(leg.crossings for leg in walk_legs),
        rough_surface_m=round(float(np.sum([0.0] + [0.0])), 1), modes=modes, generalized_cost_s=round(generalized_cost, 1),
    )
    features.rough_surface_m = round(sum(
        float(e["length_m"][i]) for i in walk_idx if str(e["surface"][i]) in ROUGH_SURFACES
    ), 1)
    return RouteOut(
        id=route_id, rank=rank, summary=_summary(legs), badges=[], cautions=[],
        total_duration_min=round(total_time / 60.0, 1), walk_distance_m=round(walk_distance, 1),
        transfers=features.transfers, origin_algorithm=origin_algorithm, features=features, legs=legs, path=full_path,
    )


def _summary(legs: list[LegOut]) -> str:
    parts: list[str] = []
    for leg in legs:
        if leg.kind == "walk":
            parts.append(f"도보 {max(1, round(leg.duration_s / 60))}분")
        elif leg.kind == "ride":
            name = leg.route_name or leg.route_id
            mode = "지하철" if leg.mode == "subway" else "버스" if leg.mode == "bus" else leg.mode
            parts.append(f"{mode} {name} {leg.stop_count}정거장")
        elif leg.kind == "vertical":
            label = {"elevator": "엘리베이터", "escalator": "에스컬레이터", "stairs": "계단", "unknown": "수직이동(확인 필요)"}[leg.facility]
            parts.append(label)
    return " · ".join(parts) if parts else "경로"


def assign_badges(routes: list[RouteOut], profile: ProfileParams, weather: WeatherContext, shade_available: bool) -> None:
    if not routes:
        return
    fastest = min(routes, key=lambda r: r.features.total_duration_s)
    fastest.badges.append("fastest")
    shortest = min(routes, key=lambda r: r.features.walk_distance_m)
    if shortest is not fastest or len(routes) == 1:
        shortest.badges.append("shortest_walk")
    with_grade = [r for r in routes if r.features.max_grade_pct is not None]
    if len(with_grade) > 1:
        gentlest = min(with_grade, key=lambda r: (r.features.max_grade_pct, r.features.avg_grade_pct or 0))
        if any(r.features.max_grade_pct > gentlest.features.max_grade_pct + 0.5 for r in with_grade):
            gentlest.badges.append("gentlest_slope")
    if shade_available:
        with_shade = [r for r in routes if r.features.shade_ratio is not None]
        if len(with_shade) > 1:
            shadiest = max(with_shade, key=lambda r: r.features.shade_ratio)
            if any(shadiest.features.shade_ratio - r.features.shade_ratio >= 0.05 for r in with_shade):
                shadiest.badges.append("most_shade")
    transfers = {r.features.transfers for r in routes}
    if len(transfers) > 1:
        min(routes, key=lambda r: r.features.transfers).badges.append("fewest_transfers")
    for r in routes:
        if r.features.stairs_count == 0 and all(leg.facility != "stairs" for leg in r.legs if leg.kind == "vertical"):
            r.badges.append("stair_free")
        verticals = [leg for leg in r.legs if leg.kind == "vertical"]
        if verticals and all(leg.facility == "elevator" for leg in verticals):
            r.badges.append("elevator_confirmed")
        # 주의사항
        f = r.features
        if f.max_grade_pct is not None and f.max_grade_pct > STEEP_CAUTION_PCT:
            r.cautions.append(f"최대 경사 {f.max_grade_pct:.0f}% 구간이 있습니다 (90m 지형 추정)")
        if f.stairs_count > 0:
            r.cautions.append(f"계단 {f.stairs_count}곳 (약 {f.total_steps}단)")
        if f.unverified_vertical_count > 0:
            r.cautions.append("엘리베이터 확인이 필요한 역 출입구가 있습니다")
        if weather.heat and f.unshaded_walk_m > UNSHADED_CAUTION_M:
            r.cautions.append(f"그늘 없는 도보 {f.unshaded_walk_m:.0f}m (더위 주의)")
        if weather.rain and (f.stairs_count > 0 or (f.max_grade_pct or 0) > 6):
            r.cautions.append("우천 시 계단·경사 구간 미끄럼 주의")
        if profile.id == "wheelchair":
            for leg in r.legs:
                if leg.kind == "ride" and leg.mode == "bus" and leg.low_floor_ratio is not None and leg.low_floor_ratio < LOW_FLOOR_CAUTION_RATIO:
                    r.cautions.append(f"{leg.route_name or leg.route_id} 버스 저상 비율 {leg.low_floor_ratio:.0%}")
                if leg.kind == "ride" and leg.mode == "bus" and leg.low_floor_ratio is None:
                    r.cautions.append(f"{leg.route_name or leg.route_id} 버스 저상 여부 미확인")
        if f.rough_surface_m > 100:
            r.cautions.append(f"비포장·요철 표면 {f.rough_surface_m:.0f}m")
