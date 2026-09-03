import numpy as np
import pytest
from shapely.geometry import LineString

from app.graph.model import TRI_FALSE, TRI_TRUE, TRI_UNKNOWN

# pandas 는 파이프라인 전용 의존성(requirements-pipeline.txt). 없으면 이 파일만 건너뛴다
pd = pytest.importorskip("pandas")
from app.pipeline.build_walk_graph import build_from_frames, load_unramped_way_ids  # noqa: E402


def _frames():
    nodes = pd.DataFrame({
        "id": [1, 2, 3, 4, 5, 6],
        "lat": [35.10, 35.10, 35.10, 35.101, 35.20, 35.20],
        "lon": [129.00, 129.001, 129.002, 129.001, 129.00, 129.001],
    })
    edges = pd.DataFrame({
        "u": [1, 2, 2, 5, 3],
        "v": [2, 3, 4, 6, 4],
        "id": [100, 101, 102, 103, 104],
        "highway": ["footway", "steps", "footway", "footway", "motorway"],
        "surface": ["asphalt", None, "gravel", None, None],
        "step_count": [None, "12", None, None, None],
        "ramp": [None, None, None, None, None],
        "width": [None, None, "0.8", None, None],
        "geometry": [
            LineString([(129.00, 35.10), (129.0005, 35.1002), (129.001, 35.10)]),
            LineString([(129.002, 35.10), (129.001, 35.10)]),   # 반대 방향으로 그려진 도형
            None, None, None,
        ],
    })
    return nodes, edges


def test_build_from_frames_bidirectional_and_tags():
    nodes, edges = _frames()
    graph, report = build_from_frames(nodes, edges, unramped_way_ids={101}, keep_largest=False)
    assert report.dropped_unwalkable == 1          # motorway
    assert report.unramped_applied == 1
    assert graph.num_edges == 8                    # 4 walkable ways × 2 directions
    assert graph.num_nodes == 6
    e = graph.edges
    steps = np.nonzero(e["stairs"] == TRI_TRUE)[0]
    assert len(steps) == 2
    assert all(e["ramp"][i] == TRI_FALSE for i in steps)
    assert all(e["step_count"][i] == 12 for i in steps)
    narrow = np.nonzero(~np.isnan(e["width_m"]))[0]
    assert len(narrow) == 2 and all(abs(e["width_m"][i] - 0.8) < 1e-6 for i in narrow)
    # 도형 방향이 u→v 로 정렬되고 역방향 엣지는 뒤집힌다
    fwd = [i for i in range(graph.num_edges) if e["source"][i] == 1 and e["target"][i] == 2][0]
    back = [i for i in range(graph.num_edges) if e["source"][i] == 2 and e["target"][i] == 1][0]
    g_f, g_b = graph.edge_geometry(fwd), graph.edge_geometry(back)
    assert len(g_f) == 3 and g_f[0] == pytest.approx((35.10, 129.00)) and g_b[0] == pytest.approx((35.10, 129.001))
    s23 = [i for i in range(graph.num_edges) if e["source"][i] == 2 and e["target"][i] == 3][0]
    assert graph.edge_geometry(s23)[0] == pytest.approx((35.10, 129.001))
    assert e["length_m"][fwd] > 80
    assert e["ramp"][fwd] == TRI_UNKNOWN


def test_largest_component_drops_island():
    nodes, edges = _frames()
    graph, report = build_from_frames(nodes, edges, keep_largest=True)
    assert report.removed_disconnected == 2
    assert set(graph.nodes["id"].tolist()) == {1, 2, 3, 4}


def test_load_unramped_way_ids(tmp_path):
    p = tmp_path / "steps.geojson"
    p.write_text('{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"osmWayId":42},"geometry":null},'
                 '{"type":"Feature","properties":{"id":"x"},"geometry":null}]}', encoding="utf-8")
    assert load_unramped_way_ids(p) == {42}
    assert load_unramped_way_ids(None) == set()
