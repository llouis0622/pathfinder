"""VWorld 실측 높이 병합 (네트워크 없이 가짜 fetch 로)."""
from app.graph.store import Building
from app.pipeline.build_buildings import bbox_cells, fetch_vworld_buildings, merge_vworld_heights


def sq(lat, lng, size=0.0004):
    return [(lat, lng), (lat, lng + size), (lat + size, lng + size), (lat + size, lng)]


def test_bbox_cells_cover_bbox():
    cells = bbox_cells((35.0, 129.0, 35.12, 129.07), step_deg=0.05)
    assert len(cells) == 3 * 2
    assert cells[0] == (35.0, 129.0, 35.05, 129.05) and cells[-1][2] == 35.12 and cells[-1][3] == 129.07


def test_fetch_dedupes_by_ufid_and_merge_fills_heights():
    def fake_fetch(cell, key):
        assert key == "k"
        # 두 셀에서 같은 ufid 가 다시 온다
        return [
            {"type": "Feature", "properties": {"ufid": "A", "height": "27.5"},
             "geometry": {"type": "Polygon", "coordinates": [[(129.0001, 35.0001), (129.0004, 35.0001), (129.0004, 35.0004), (129.0001, 35.0004), (129.0001, 35.0001)]]}},
            {"type": "Feature", "properties": {"ufid": "B", "height": "0"},
             "geometry": {"type": "Polygon", "coordinates": [[(129.02, 35.02), (129.0204, 35.02), (129.0204, 35.0204), (129.02, 35.0204), (129.02, 35.02)]]}},
        ]

    vworld = fetch_vworld_buildings((35.0, 129.0, 35.08, 129.08), "k", step_deg=0.05, fetch=fake_fetch)
    assert len(vworld) == 2 and vworld[0].height_m == 27.5 and vworld[1].height_m is None
    osm = [
        Building(id=1, height_m=None, footprint=sq(35.0001, 129.0001), holes=[]),   # A 와 겹침 → 높이 채움
        Building(id=2, height_m=12.0, footprint=sq(35.0001, 129.0001), holes=[]),   # 이미 높이 있음 → 유지
        Building(id=3, height_m=None, footprint=sq(35.05, 129.05), holes=[]),       # 겹치는 VWorld 없음 → 그대로
    ]
    merged, rep = merge_vworld_heights(osm, vworld)
    assert rep == {"filled": 1, "added": 1, "vworld": 2}
    by_id = {b.id: b for b in merged}
    assert by_id[1].height_m == 27.5 and by_id[2].height_m == 12.0 and by_id[3].height_m is None
    assert len(merged) == 4 and merged[-1].id == vworld[1].id   # B 는 OSM 과 안 겹쳐 추가됨
    assert merge_vworld_heights(osm, [])[1] == {"filled": 0, "added": 0, "vworld": 0}
