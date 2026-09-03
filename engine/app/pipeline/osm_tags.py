"""OSM 태그 → 그래프 엣지 속성 파생 (순수 함수, 테스트 대상)."""
from __future__ import annotations

import re
from typing import Any

WALK_TAGS = (
    "highway", "footway", "surface", "width", "incline", "step_count", "ramp", "ramp:wheelchair", "handrail",
    "tactile_paving", "kerb", "crossing", "crossing:markings", "lit", "wheelchair", "sidewalk", "tunnel", "bridge",
    "level", "indoor", "name", "smoothness", "access", "foot", "oneway", "service", "layer", "covered",
)

_NUMBER = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def _first(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def parse_float(value: Any) -> float | None:
    """'1.5', '1,5', '2 m', '150 cm', '3\\'' 등 → 미터."""
    value = _first(value)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value == value else None
    s = str(value).strip().lower()
    if not s:
        return None
    m = _NUMBER.search(s)
    if not m:
        return None
    num = float(m.group(0).replace(",", "."))
    if "cm" in s:
        return num / 100.0
    if "mm" in s:
        return num / 1000.0
    if "'" in s or "ft" in s:
        return num * 0.3048
    return num


def parse_int(value: Any) -> int | None:
    f = parse_float(value)
    return None if f is None else int(round(f))


def yes_no(value: Any) -> bool | None:
    value = _first(value)
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("yes", "true", "1", "designated", "limited", "both", "left", "right", "separate"):
        return True
    if s in ("no", "false", "0", "none"):
        return False
    return None


def parse_height(tags: dict[str, Any]) -> tuple[float | None, str]:
    h = parse_float(tags.get("height"))
    if h is not None and 0 < h <= 1000:
        return h, "osm:height"
    levels = parse_float(tags.get("building:levels"))
    if levels is not None and 0 < levels <= 200:
        return levels * 3.3, "osm:levels"
    return None, ""


def derive_walk_attrs(tags: dict[str, Any]) -> dict[str, Any]:
    """pyrosm/osmnx 엣지 태그 → 엣지 레코드 속성."""
    t = {k: _first(v) for k, v in tags.items() if v is not None and not (isinstance(v, float) and v != v)}
    highway = str(t.get("highway") or "")
    footway = str(t.get("footway") or "")
    stairs = highway == "steps"
    ramp = yes_no(t.get("ramp:wheelchair"))
    if ramp is None and stairs:
        r = str(t.get("ramp") or "").lower()
        if r == "no":
            ramp = False
    crossing = ""
    if footway == "crossing" or highway == "crossing":
        c = str(t.get("crossing") or "").lower()
        markings = str(t.get("crossing:markings") or "").lower()
        if c in ("traffic_signals", "pelican", "toucan", "pedestrian_signals"):
            crossing = "traffic_signals"
        elif c in ("marked", "zebra", "uncontrolled") or markings in ("yes", "zebra"):
            crossing = "marked"
        elif c in ("unmarked", "informal"):
            crossing = "unmarked"
        else:
            crossing = "unknown"
    kerb = str(t.get("kerb") or "").lower()
    if kerb not in ("raised", "lowered", "flush", "rolled", "no"):
        kerb = ""
    tunnel = str(t.get("tunnel") or "").lower()
    indoor_tag = str(t.get("indoor") or "").lower()
    covered = str(t.get("covered") or "").lower()
    indoor = tunnel in ("yes", "building_passage") or indoor_tag in ("yes", "corridor", "area", "room") or covered == "yes"
    return {
        "kind": "walk",
        "mode": "walk",
        "stairs": stairs,
        "step_count": parse_int(t.get("step_count")) if stairs else None,
        "ramp": ramp,
        "handrail": yes_no(t.get("handrail")),
        "surface": str(t.get("surface") or "").lower(),
        "width_m": parse_float(t.get("width")),
        "tactile": yes_no(t.get("tactile_paving")),
        "crossing": crossing,
        "kerb": kerb,
        "lit": yes_no(t.get("lit")),
        "indoor": indoor,
    }


def is_walkable(tags: dict[str, Any]) -> bool:
    """pyrosm walking 필터 위에 추가로 제외할 것: 자동차 전용·사유지 접근 금지."""
    t = {k: _first(v) for k, v in tags.items()}
    highway = str(t.get("highway") or "")
    if highway in ("motorway", "motorway_link", "trunk", "trunk_link", "construction", "proposed", "raceway"):
        return False
    foot = str(t.get("foot") or "").lower()
    access = str(t.get("access") or "").lower()
    if foot == "no":
        return False
    if access in ("private", "no") and foot not in ("yes", "designated", "permissive"):
        return False
    return True
