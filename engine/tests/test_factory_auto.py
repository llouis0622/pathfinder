"""GRAPH_SOURCE=auto: PostGIS → 빌드 산출물 → 샘플 순서로 고른다. DATABASE_URL 형식도 관대하게 받는다."""
from pathlib import Path

from app.config import Settings, plain_postgres_url
from app.graph import factory
from app.graph.factory import build_store, resolve_auto

SAMPLE = str(Path(__file__).resolve().parents[2] / "data" / "samples" / "grid_city.npz")
SAMPLE_B = str(Path(__file__).resolve().parents[2] / "data" / "samples" / "grid_city_buildings.json")


def test_auto_falls_back_to_sample_without_db_or_build(tmp_path):
    src, bundle, blds, why = resolve_auto(bundle_path=SAMPLE, buildings_path=SAMPLE_B, dsn="postgresql://x:y@127.0.0.1:1/nope", build_dir=str(tmp_path))
    assert src == "file" and bundle == SAMPLE and "샘플" in why
    store = build_store("auto", bundle_path=SAMPLE, buildings_path=SAMPLE_B, dsn="", build_dir=str(tmp_path))
    d = store.describe()
    assert d["sample"] is True and d["nodes"] > 0 and "샘플" in d["resolved_from"]


def test_auto_prefers_build_dir_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(factory, "postgis_has_graph", lambda dsn, timeout_s=3.0: False)
    (tmp_path / "graph_bundle.npz").write_bytes(Path(SAMPLE).read_bytes())
    src, bundle, blds, why = resolve_auto(bundle_path=SAMPLE, buildings_path=SAMPLE_B, dsn="postgresql://ignored", build_dir=str(tmp_path))
    assert src == "file" and bundle.endswith("graph_bundle.npz") and blds == "" and "산출물" in why
    store = build_store("auto", bundle_path=SAMPLE, buildings_path=SAMPLE_B, dsn="", build_dir=str(tmp_path))
    assert store.describe()["sample"] is False


def test_auto_prefers_postgis_when_graph_present(monkeypatch):
    monkeypatch.setattr(factory, "postgis_has_graph", lambda dsn, timeout_s=3.0: True)
    src, *_rest, why = resolve_auto(bundle_path=SAMPLE, buildings_path=SAMPLE_B, dsn="postgresql://db", build_dir="")
    assert src == "postgis_memory" and "PostGIS" in why


def test_database_url_accepts_backend_style_prefix():
    assert plain_postgres_url("postgresql+asyncpg://u:p@h:5432/d") == "postgresql://u:p@h:5432/d"
    assert plain_postgres_url("postgres://u:p@h/d") == "postgresql://u:p@h/d"
    s = Settings(database_url="postgresql+asyncpg://u:p@h:5432/d", _env_file=None)
    assert s.database_url == "postgresql://u:p@h:5432/d" and s.graph_source == "auto"
