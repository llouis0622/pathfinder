"""엣지 비용 계산 (벡터화).

`compute_costs()`는 두 배열을 돌려준다.
- `time_s`: 프로필 속도와 물리적 지연만 반영한 순수 이동 시간
- `cost`: 일반화 비용(초). 부담 패널티·날씨 배율 포함. 차단 엣지는 +inf
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..graph.model import TRI_FALSE, TRI_TRUE, TRI_UNKNOWN, Graph
from .profiles import SURFACE_CLASS, ProfileParams
from .weather import WeatherContext

MAX_WAIT_S = 900.0
DEFAULT_HEADWAY_S = 600.0
DEFAULT_STEP_COUNT = 12.0
STAIRS_PHYSICAL_S_PER_STEP = 1.0

BLOCK_NONE = 0
BLOCK_STAIRS = 1
BLOCK_SLOPE = 2
BLOCK_WIDTH = 3
BLOCK_KERB = 4
BLOCK_VERTICAL = 5
BLOCK_LOW_FLOOR = 6

BLOCK_LABELS = {
    BLOCK_STAIRS: "경사로 없는 계단",
    BLOCK_SLOPE: "경사 한계 초과",
    BLOCK_WIDTH: "보도 폭 부족",
    BLOCK_KERB: "턱 있는 연석",
    BLOCK_VERTICAL: "엘리베이터 없는 수직 이동",
    BLOCK_LOW_FLOOR: "저상버스 없는 노선",
}


@dataclass
class CostResult:
    time_s: np.ndarray
    cost: np.ndarray
    blocked: np.ndarray          # int8 사유 코드
    unverified: np.ndarray       # bool: 미확인 시설을 지나는 엣지(주의 표시용)
    transfer_penalty_s: float

    @property
    def n_blocked(self) -> int:
        return int(np.count_nonzero(self.blocked))


def _surface_factor(profile: ProfileParams, surface: np.ndarray) -> np.ndarray:
    classes = np.array([SURFACE_CLASS.get(s, "" if s == "" else "paved") for s in surface])
    return np.array([profile.surface_factor.get(c, 1.0) for c in classes], dtype=np.float64)


def compute_costs(
    graph: Graph,
    profile: ProfileParams,
    weather: WeatherContext | None = None,
    shade_ratio: np.ndarray | None = None,
) -> CostResult:
    weather = weather or WeatherContext.none()
    E = graph.num_edges
    e = graph.edges
    kind = e["kind"]
    time_s = np.zeros(E, dtype=np.float64)
    cost = np.zeros(E, dtype=np.float64)
    blocked = np.zeros(E, dtype=np.int8)
    unverified = np.zeros(E, dtype=bool)
    if E == 0:
        return CostResult(time_s, cost, blocked, unverified, profile.transfer_penalty_s)

    length = e["length_m"].astype(np.float64)
    grade = np.nan_to_num(e["grade_pct"].astype(np.float64), nan=0.0)
    outdoor = e["indoor"] != TRI_TRUE
    shade = np.zeros(E) if shade_ratio is None else np.clip(np.nan_to_num(shade_ratio, nan=0.0), 0.0, 1.0)
    rain_mult = 1.5 if weather.rain else 1.0

    # ---------- 보행 (walk, link) ----------
    walk = (kind == "walk") | (kind == "link")
    if walk.any():
        g_abs = np.abs(grade)
        a = np.where(grade > 0, profile.slope_up, profile.slope_down)
        t = length / profile.speed_mps * (1.0 + a * g_abs)
        sf = _surface_factor(profile, e["surface"])
        t = t * sf
        c = t.copy()
        # 급경사 추가 부담
        steep = g_abs > profile.slope_soft_pct
        c = c + np.where(steep, length * profile.steep_extra_s_per_m * rain_mult, 0.0)
        if profile.slope_hard_pct is not None:
            hard = walk & (g_abs > profile.slope_hard_pct)
            blocked[hard] = BLOCK_SLOPE
        # 계단
        stairs = e["stairs"] == TRI_TRUE
        if stairs.any():
            steps = np.nan_to_num(e["step_count"].astype(np.float64), nan=DEFAULT_STEP_COUNT)
            steps = np.where(steps <= 0, DEFAULT_STEP_COUNT, steps)
            if profile.stairs_blocked_without_ramp:
                ramp_ok = e["ramp"] == TRI_TRUE
                blocked[walk & stairs & ~ramp_ok] = BLOCK_STAIRS
            else:
                handrail = np.where(e["handrail"] == TRI_TRUE, profile.stairs_handrail_factor, 1.0)
                pen = (profile.stairs_base_s + profile.stairs_per_step_s * steps) * handrail * rain_mult
                c = c + np.where(stairs, pen, 0.0)
                t = t + np.where(stairs, steps * STAIRS_PHYSICAL_S_PER_STEP, 0.0)
        # 폭
        width = e["width_m"].astype(np.float64)
        has_width = ~np.isnan(width)
        if profile.min_width_m is not None:
            blocked[walk & has_width & (width < profile.min_width_m) & (blocked == 0)] = BLOCK_WIDTH
        if profile.narrow_width_m is not None:
            narrow = has_width & (width < profile.narrow_width_m)
            c = c + np.where(narrow, length * profile.narrow_extra_s_per_m, 0.0)
        # 횡단보도
        crossing = e["crossing"]
        is_signals = crossing == "traffic_signals"
        is_marked = (crossing == "marked") | (crossing == "zebra") | (crossing == "uncontrolled")
        is_unmarked = (crossing != "") & ~is_signals & ~is_marked
        c = c + np.where(is_signals, profile.crossing_signals_s, 0.0)
        t = t + np.where(is_signals, profile.crossing_signals_s, 0.0)
        c = c + np.where(is_marked, profile.crossing_marked_s, 0.0)
        c = c + np.where(is_unmarked, profile.crossing_unmarked_s, 0.0)
        if profile.crossing_no_tactile_extra_s:
            c = c + np.where((crossing != "") & (e["tactile"] == TRI_FALSE), profile.crossing_no_tactile_extra_s, 0.0)
        kerb_raised = e["kerb"] == "raised"
        if profile.kerb_raised_blocked:
            blocked[walk & kerb_raised & (blocked == 0)] = BLOCK_KERB
        else:
            c = c + np.where(kerb_raised, profile.kerb_raised_s, 0.0)
        # 점자블록
        if profile.tactile_yes_factor != 1.0:
            c = c * np.where(e["tactile"] == TRI_TRUE, profile.tactile_yes_factor, 1.0)
        if profile.tactile_no_sidewalk_factor != 1.0:
            c = c * np.where((e["tactile"] == TRI_FALSE) & (crossing == ""), profile.tactile_no_sidewalk_factor, 1.0)
        # 날씨 (실외)
        wmult = np.ones(E)
        if weather.heat:
            h = profile.heat_factor * (2.0 if weather.heatwave else 1.0)
            wmult = wmult * (1.0 + h * (1.0 - shade))
        if weather.cold:
            wmult = wmult * (profile.coldwave_factor if weather.coldwave else profile.cold_factor)
        if weather.rain:
            wmult = wmult * profile.rain_factor
            slippery = np.isin(e["surface"], ["cobblestone", "sett", "unhewn_cobblestone", "unpaved", "dirt", "ground", "grass", "sand", "mud", "earth"])
            wmult = wmult * np.where(slippery, 1.2, 1.0)
        if weather.bad_air:
            wmult = wmult * profile.bad_air_factor
        if weather.windy:
            wmult = wmult * profile.windy_factor
        c = c * np.where(outdoor, wmult, 1.0)
        time_s[walk] = t[walk]
        cost[walk] = c[walk]

    # ---------- 수직 이동 ----------
    vertical = kind == "vertical"
    if vertical.any():
        elev = e["elevator"]
        esc = e["escalator"]
        vt = np.full(E, np.nan)
        vc = np.full(E, np.nan)
        for mask, seconds, penalty in (
            (elev == TRI_TRUE, profile.vertical_elevator_s, 0.0),
            ((elev == TRI_FALSE) & (esc == TRI_TRUE), profile.vertical_escalator_s, 0.0),
            ((elev == TRI_FALSE) & (esc != TRI_TRUE), profile.vertical_stairs_s, 0.0),
            (elev == TRI_UNKNOWN, profile.vertical_unknown_s, profile.vertical_unknown_penalty_s),
        ):
            m = vertical & mask
            if seconds is None:
                blocked[m] = BLOCK_VERTICAL
                vt[m] = 0.0
                vc[m] = 0.0
            else:
                vt[m] = seconds
                vc[m] = seconds + penalty
        unverified |= vertical & (elev == TRI_UNKNOWN)
        time_s[vertical] = np.nan_to_num(vt[vertical])
        cost[vertical] = np.nan_to_num(vc[vertical])

    # ---------- 승차 ----------
    board = kind == "board"
    if board.any():
        headway = np.nan_to_num(e["headway_s"].astype(np.float64), nan=DEFAULT_HEADWAY_S)
        wait = np.minimum(headway / 2.0, MAX_WAIT_S)
        is_bus = e["mode"] == "bus"
        boarding = np.where(is_bus, profile.boarding_bus_s, profile.boarding_subway_s) + profile.boarding_extra_s
        lfr = e["low_floor_ratio"].astype(np.float64)
        if profile.bus_requires_low_floor:
            known = ~np.isnan(lfr)
            blocked[board & is_bus & known & (lfr <= 0.0)] = BLOCK_LOW_FLOOR
            ratio = np.where(known & (lfr > 0.0), lfr, 1.0)
            wait = np.where(is_bus, np.minimum(wait / ratio, MAX_WAIT_S * 2), wait)
            unverified |= board & is_bus & ~known
        bt = wait + boarding
        bc = bt + profile.transfer_penalty_s
        if weather.cold:
            bc = bc + np.where(outdoor, wait * 0.5, 0.0)
        time_s[board] = bt[board]
        cost[board] = bc[board]

    # ---------- 하차 ----------
    alight = kind == "alight"
    if alight.any():
        is_bus = e["mode"] == "bus"
        at = np.where(is_bus, profile.alight_bus_s, profile.alight_subway_s)
        time_s[alight] = at[alight]
        cost[alight] = at[alight]

    # ---------- 탑승 ----------
    ride = kind == "ride"
    if ride.any():
        rt = np.nan_to_num(e["time_s"].astype(np.float64), nan=0.0)
        time_s[ride] = rt[ride]
        cost[ride] = rt[ride]

    # ---------- 기타 (transfer) ----------
    other = ~(walk | vertical | board | alight | ride)
    if other.any():
        ot = np.nan_to_num(e["time_s"].astype(np.float64), nan=length / profile.speed_mps)
        time_s[other] = ot[other]
        cost[other] = ot[other]

    cost = np.where(blocked != 0, np.inf, cost)
    cost = np.maximum(cost, 1e-3)
    return CostResult(time_s, cost, blocked, unverified, profile.transfer_penalty_s)


def route_cost(edge_path, cost: CostResult, graph: Graph) -> float:
    """경로 총 비용. 첫 승차의 환승 패널티는 돌려준다."""
    idx = np.asarray(edge_path, dtype=np.int64)
    if idx.size == 0:
        return 0.0
    total = float(np.sum(cost.cost[idx]))
    if np.isinf(total):
        return float("inf")
    boards = int(np.count_nonzero(graph.edges["kind"][idx] == "board"))
    if boards > 0:
        total -= cost.transfer_penalty_s
    return total
