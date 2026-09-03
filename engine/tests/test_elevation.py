import numpy as np
import pytest

from app.features.elevation import DEFAULT_DEM, Dem, enrich_elevation
from app.graph.model import Graph

pytestmark = pytest.mark.skipif(not DEFAULT_DEM.is_file(), reason="부산 DEM 파일 없음")


@pytest.fixture(scope="module")
def dem():
    return Dem.load()


def test_dem_samples_known_points(dem):
    # 부산역 앞(저지대) vs 금정산 고당봉 부근(고지대), 바다(결측)
    z = dem.sample(np.array([35.1151, 35.2830, 35.05]), np.array([129.0403, 129.0540, 129.20]))
    assert 0 <= z[0] < 60
    assert z[1] > 500
    assert np.isnan(z[2]) or z[2] < 10
    assert dem.resolution_m == pytest.approx(90.0)


def test_enrich_elevation_sets_grades(dem):
    # 부산대역 → 금정산 방향으로 오르는 3개 노드 사슬
    pts = [(35.2296, 129.0893), (35.2340, 129.0800), (35.2400, 129.0700)]
    nodes = [{"id": i, "kind": "walk", "lat": p[0], "lng": p[1]} for i, p in enumerate(pts)]
    edges = []
    eid = 1
    for i in range(2):
        from app.graph.geo import haversine_m

        L = float(haversine_m(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]))
        for a, b in ((i, i + 1), (i + 1, i)):
            edges.append({"id": eid, "source": a, "target": b, "kind": "walk", "length_m": L})
            eid += 1
    edges.append({"id": eid, "source": 0, "target": 1, "kind": "ride", "mode": "subway", "length_m": 100, "time_s": 60})
    g = Graph.from_records(nodes, edges)
    g, report = enrich_elevation(g, dem)
    assert report.nodes_measured == 3 and report.edges_graded == 4 and report.edges_total == 4
    grade = g.edges["grade_pct"]
    assert np.isnan(grade[4])                              # ride 엣지는 경사 없음
    assert grade[0] == pytest.approx(-grade[1], abs=1e-4)  # 역방향은 부호 반전
    assert grade[0] > 0                                     # 산 쪽으로 오르막
    assert g.edges["max_grade_pct"][0] >= abs(grade[0]) - 1e-4
    assert np.all(np.abs(grade[:4]) <= 35.0)
    assert not np.isnan(g.nodes["elevation_m"]).any()
