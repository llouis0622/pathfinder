"""설정에 따라 GraphStore를 만든다.

GRAPH_SOURCE
- auto            : 아래 순서로 처음 되는 것을 쓴다 → PostGIS 에 그래프가 있으면 postgis_memory,
                    없으면 GRAPH_BUILD_DIR/graph_bundle.npz(run_all 산출물), 그것도 없으면 샘플 격자 도시(GRAPH_BUNDLE_PATH)
- file            : GRAPH_BUNDLE_PATH(npz) + BUILDINGS_PATH(json)를 메모리에 적재
- postgis         : 요청마다 PostGIS에서 회랑을 SQL로 추출
- postgis_memory  : 시작 시 PostGIS 전체를 메모리에 적재(부산 전체도 수 초), 이후 file 모드처럼 동작
"""
from __future__ import annotations

import logging
from pathlib import Path

from .store import GraphStore, MemoryGraphStore

log = logging.getLogger("graph.factory")
BUNDLE_NAME = "graph_bundle.npz"
BUILDINGS_NAME = "buildings.json"


def postgis_has_graph(dsn: str, timeout_s: float = 3.0) -> bool:
    """PostGIS 에 접속되고 graph_meta.node_count > 0 이면 True. 접속 실패·스키마 없음은 False (예외 없음)."""
    if not dsn:
        return False
    try:
        import psycopg

        with psycopg.connect(dsn, connect_timeout=int(timeout_s)) as conn:
            row = conn.execute("SELECT value FROM graph_meta WHERE key = 'node_count'").fetchone()
            return bool(row and int(row[0]) > 0)
    except Exception as exc:  # noqa: BLE001  (연결 실패, 테이블 없음 등은 모두 '그래프 없음')
        log.info("PostGIS 그래프 없음 (%s: %s)", type(exc).__name__, str(exc).strip().splitlines()[0][:120] if str(exc) else "")
        return False


def resolve_auto(*, bundle_path: str, buildings_path: str, dsn: str, build_dir: str) -> tuple[str, str, str, str]:
    """auto 모드 결정. (source, bundle_path, buildings_path, reason) 을 돌려준다."""
    if postgis_has_graph(dsn):
        return "postgis_memory", bundle_path, buildings_path, "PostGIS 에 적재된 그래프"
    built = Path(build_dir) / BUNDLE_NAME if build_dir else None
    if built and built.is_file():
        b = Path(build_dir) / BUILDINGS_NAME
        return "file", str(built), (str(b) if b.is_file() else ""), f"파이프라인 산출물 {built}"
    return "file", bundle_path, buildings_path, "샘플 격자 도시 (PostGIS·빌드 산출물 없음)"


def build_store(source: str, *, bundle_path: str = "", buildings_path: str = "", dsn: str = "", build_dir: str = "") -> GraphStore:
    source = (source or "auto").lower()
    resolved_from = ""
    if source == "auto":
        source, bundle_path, buildings_path, resolved_from = resolve_auto(bundle_path=bundle_path, buildings_path=buildings_path, dsn=dsn, build_dir=build_dir)
        log.warning("GRAPH_SOURCE=auto → %s (%s)", source, resolved_from)
    if source == "file":
        if not Path(bundle_path).is_file():
            raise FileNotFoundError(f"그래프 번들이 없습니다: {bundle_path}")
        store = MemoryGraphStore.from_npz(bundle_path, buildings_path or None)
        store.resolved_from = resolved_from  # type: ignore[attr-defined]
        log.info("메모리 그래프 적재 %s", store.describe())
        return store
    from .postgis import PostgisGraphStore

    pg = PostgisGraphStore(dsn)
    if source == "postgis":
        log.info("PostGIS 스토어 %s", pg.describe())
        return pg
    if source == "postgis_memory":
        graph = pg.load_full()
        buildings = pg.load_all_buildings()
        store = MemoryGraphStore(graph, buildings, source="postgis_memory")
        store.resolved_from = resolved_from  # type: ignore[attr-defined]
        log.info("PostGIS → 메모리 적재 %s", store.describe())
        return store
    raise ValueError(f"알 수 없는 GRAPH_SOURCE: {source}")
