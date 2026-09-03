"""설정에 따라 GraphStore를 만든다.

GRAPH_SOURCE
- file            : GRAPH_BUNDLE_PATH(npz) + BUILDINGS_PATH(json)를 메모리에 적재
- postgis         : 요청마다 PostGIS에서 회랑을 SQL로 추출
- postgis_memory  : 시작 시 PostGIS 전체를 메모리에 적재(부산 전체도 수 초), 이후 file 모드처럼 동작
"""
from __future__ import annotations

import logging
from pathlib import Path

from .store import GraphStore, MemoryGraphStore

log = logging.getLogger("graph.factory")


def build_store(source: str, *, bundle_path: str = "", buildings_path: str = "", dsn: str = "") -> GraphStore:
    source = (source or "file").lower()
    if source == "file":
        if not Path(bundle_path).is_file():
            raise FileNotFoundError(f"그래프 번들이 없습니다: {bundle_path}")
        store = MemoryGraphStore.from_npz(bundle_path, buildings_path or None)
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
        log.info("PostGIS → 메모리 적재 %s", store.describe())
        return store
    raise ValueError(f"알 수 없는 GRAPH_SOURCE: {source}")
