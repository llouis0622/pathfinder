from app.pipeline.osm_tags import derive_walk_attrs, is_walkable, parse_float, parse_height, yes_no


def test_parse_float_units():
    assert parse_float("1.5") == 1.5
    assert parse_float("1,5") == 1.5
    assert parse_float("150 cm") == 1.5
    assert parse_float("2 m") == 2.0
    assert parse_float("6'") == 6 * 0.3048
    assert parse_float(None) is None
    assert parse_float("wide") is None
    assert parse_float(float("nan")) is None
    assert parse_float(["3", "4"]) == 3.0


def test_yes_no():
    assert yes_no("yes") is True and yes_no("no") is False and yes_no("maybe") is None and yes_no(None) is None


def test_parse_height_prefers_height_then_levels():
    assert parse_height({"height": "24.5"}) == (24.5, "osm:height")
    assert parse_height({"building:levels": "5"}) == (16.5, "osm:levels")
    assert parse_height({"height": "9999"}) == (None, "")
    assert parse_height({}) == (None, "")


def test_derive_steps_with_ramp_no():
    a = derive_walk_attrs({"highway": "steps", "step_count": "24", "ramp": "no", "handrail": "yes", "surface": "concrete"})
    assert a["stairs"] is True and a["step_count"] == 24 and a["ramp"] is False and a["handrail"] is True
    b = derive_walk_attrs({"highway": "steps", "ramp:wheelchair": "yes"})
    assert b["ramp"] is True and b["step_count"] is None
    c = derive_walk_attrs({"highway": "steps"})
    assert c["ramp"] is None


def test_derive_crossing_kerb_tactile_indoor():
    a = derive_walk_attrs({"highway": "footway", "footway": "crossing", "crossing": "traffic_signals", "tactile_paving": "no", "kerb": "lowered"})
    assert a["crossing"] == "traffic_signals" and a["tactile"] is False and a["kerb"] == "lowered" and a["stairs"] is False
    b = derive_walk_attrs({"highway": "footway", "footway": "crossing", "crossing": "zebra"})
    assert b["crossing"] == "marked"
    c = derive_walk_attrs({"highway": "footway", "footway": "crossing", "crossing:markings": "yes"})
    assert c["crossing"] == "marked"
    d = derive_walk_attrs({"highway": "footway", "footway": "crossing"})
    assert d["crossing"] == "unknown"
    e = derive_walk_attrs({"highway": "footway", "tunnel": "building_passage", "width": "2.5", "lit": "yes"})
    assert e["indoor"] is True and e["width_m"] == 2.5 and e["lit"] is True and e["crossing"] == ""
    f = derive_walk_attrs({"highway": "footway", "footway": "sidewalk", "surface": "Paving_Stones"})
    assert f["surface"] == "paving_stones" and f["indoor"] is False


def test_is_walkable():
    assert is_walkable({"highway": "footway"})
    assert not is_walkable({"highway": "motorway"})
    assert not is_walkable({"highway": "footway", "foot": "no"})
    assert not is_walkable({"highway": "service", "access": "private"})
    assert is_walkable({"highway": "service", "access": "private", "foot": "yes"})
