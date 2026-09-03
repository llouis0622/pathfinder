"""프로필별 비용 상수. 값의 근거와 단위는 docs/COST_MODEL.md 를 따른다."""
from __future__ import annotations

from dataclasses import dataclass, field

PROFILE_IDS = ("wheelchair", "elderly", "walking_aid", "visually_impaired")

SURFACE_CLASS: dict[str, str] = {
    "asphalt": "paved", "concrete": "paved", "paved": "paved", "paving_stones": "paved",
    "concrete:plates": "paved", "concrete:lanes": "paved", "metal": "paved", "wood": "paved",
    "cobblestone": "cobble", "sett": "cobble", "unhewn_cobblestone": "cobble",
    "gravel": "gravel", "fine_gravel": "gravel", "compacted": "gravel", "pebblestone": "gravel",
    "unpaved": "rough", "dirt": "rough", "ground": "rough", "grass": "rough", "sand": "rough",
    "earth": "rough", "mud": "rough",
}


@dataclass(frozen=True)
class ProfileParams:
    id: str
    label: str
    speed_mps: float
    # 경사
    slope_up: float
    slope_down: float
    slope_soft_pct: float
    slope_hard_pct: float | None          # 초과 시 차단(None이면 차단 없음)
    steep_extra_s_per_m: float = 1.5
    # 선호(preferences) 가중: avoid_slope 시 비용 ×(1 + slope_avoid_gain × 최대경사%), prefer_shade 시 ×(1 + shade_prefer_gain × (1-그늘))
    slope_avoid_gain: float = 0.10
    shade_prefer_gain: float = 0.6
    # 계단
    stairs_blocked_without_ramp: bool = False
    stairs_base_s: float = 0.0
    stairs_per_step_s: float = 0.0
    stairs_handrail_factor: float = 1.0
    # 표면 배율
    surface_factor: dict[str, float] = field(default_factory=lambda: {"paved": 1.0, "cobble": 1.0, "gravel": 1.0, "rough": 1.0, "": 1.0})
    # 폭
    min_width_m: float | None = None      # 미만 차단
    narrow_width_m: float | None = None   # 미만이면 narrow_extra_s_per_m
    narrow_extra_s_per_m: float = 0.0
    # 횡단
    crossing_signals_s: float = 20.0
    crossing_marked_s: float = 10.0
    crossing_unmarked_s: float = 15.0
    crossing_no_tactile_extra_s: float = 0.0
    kerb_raised_blocked: bool = False
    kerb_raised_s: float = 0.0
    # 점자블록
    tactile_yes_factor: float = 1.0
    tactile_no_sidewalk_factor: float = 1.0
    # 날씨
    heat_factor: float = 0.5
    cold_factor: float = 1.3
    coldwave_factor: float = 1.5
    rain_factor: float = 1.25
    bad_air_factor: float = 1.2
    windy_factor: float = 1.0
    # 수직 이동 (초). None은 차단
    vertical_elevator_s: float | None = 90.0
    vertical_escalator_s: float | None = 70.0
    vertical_stairs_s: float | None = 150.0
    vertical_unknown_s: float | None = 120.0
    vertical_unknown_penalty_s: float = 0.0
    # 승하차
    boarding_subway_s: float = 30.0
    boarding_bus_s: float = 20.0
    boarding_extra_s: float = 0.0
    alight_bus_s: float = 10.0
    alight_subway_s: float = 10.0
    bus_requires_low_floor: bool = False
    transfer_penalty_s: float = 240.0


PROFILES: dict[str, ProfileParams] = {
    "wheelchair": ProfileParams(
        id="wheelchair", label="휠체어 이용자", speed_mps=1.0,
        slope_up=0.25, slope_down=0.10, slope_soft_pct=5.0, slope_hard_pct=10.0, slope_avoid_gain=0.14,
        stairs_blocked_without_ramp=True,
        surface_factor={"paved": 1.0, "cobble": 1.6, "gravel": 1.5, "rough": 1.8, "": 1.0},
        min_width_m=0.9, narrow_width_m=1.2, narrow_extra_s_per_m=0.5,
        crossing_signals_s=20.0, crossing_marked_s=10.0, crossing_unmarked_s=15.0,
        kerb_raised_blocked=True,
        heat_factor=0.5, windy_factor=1.15,
        vertical_elevator_s=90.0, vertical_escalator_s=None, vertical_stairs_s=None,
        vertical_unknown_s=90.0, vertical_unknown_penalty_s=600.0,
        boarding_subway_s=30.0, boarding_bus_s=120.0, alight_bus_s=60.0,
        bus_requires_low_floor=True, transfer_penalty_s=300.0,
    ),
    "elderly": ProfileParams(
        id="elderly", label="고령자", speed_mps=0.85,
        slope_up=0.12, slope_down=0.05, slope_soft_pct=6.0, slope_hard_pct=None, slope_avoid_gain=0.10,
        stairs_base_s=25.0, stairs_per_step_s=3.0,
        surface_factor={"paved": 1.0, "cobble": 1.15, "gravel": 1.15, "rough": 1.2, "": 1.0},
        kerb_raised_s=10.0,
        heat_factor=0.6, bad_air_factor=1.3,
        vertical_elevator_s=90.0, vertical_escalator_s=70.0, vertical_stairs_s=150.0, vertical_unknown_s=120.0,
        boarding_extra_s=30.0, transfer_penalty_s=240.0,
    ),
    "walking_aid": ProfileParams(
        id="walking_aid", label="보행보조기·목발 이용자", speed_mps=0.7,
        slope_up=0.15, slope_down=0.10, slope_soft_pct=6.0, slope_hard_pct=None, slope_avoid_gain=0.12,
        stairs_base_s=45.0, stairs_per_step_s=5.0,
        surface_factor={"paved": 1.0, "cobble": 1.4, "gravel": 1.3, "rough": 1.5, "": 1.0},
        kerb_raised_s=20.0,
        heat_factor=0.6,
        vertical_elevator_s=90.0, vertical_escalator_s=90.0, vertical_stairs_s=240.0, vertical_unknown_s=150.0,
        boarding_extra_s=30.0, transfer_penalty_s=300.0,
    ),
    "visually_impaired": ProfileParams(
        id="visually_impaired", label="시각장애인", speed_mps=0.9,
        slope_up=0.08, slope_down=0.03, slope_soft_pct=8.0, slope_hard_pct=None, slope_avoid_gain=0.06,
        stairs_base_s=20.0, stairs_per_step_s=2.0, stairs_handrail_factor=0.5,
        surface_factor={"paved": 1.0, "cobble": 1.15, "gravel": 1.1, "rough": 1.2, "": 1.0},
        crossing_signals_s=20.0, crossing_marked_s=45.0, crossing_unmarked_s=90.0,
        crossing_no_tactile_extra_s=40.0,
        tactile_yes_factor=0.85, tactile_no_sidewalk_factor=1.15,
        heat_factor=0.3,
        vertical_elevator_s=100.0, vertical_escalator_s=80.0, vertical_stairs_s=120.0, vertical_unknown_s=110.0,
        transfer_penalty_s=360.0,
    ),
}


def get_profile(profile_id: str) -> ProfileParams:
    try:
        return PROFILES[profile_id]
    except KeyError as exc:
        raise ValueError(f"지원하지 않는 프로필: {profile_id}. 가능: {', '.join(PROFILE_IDS)}") from exc
