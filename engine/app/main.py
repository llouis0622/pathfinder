"""Pathfinder 엔진 FastAPI 앱.

시작 시 GRAPH_SOURCE 설정에 따라 그래프 스토어를 적재하고, /api/search 로 ACO+GA 탐색을 제공한다.
탐색은 CPU 작업이므로 동기 엔드포인트(스레드풀)로 둔다.
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from . import tiles
from .api.routes import router
from .config import Settings, settings
from .graph.factory import build_store
from .graph.store import GraphStore

log = logging.getLogger("engine")


def create_app(store: GraphStore | None = None, config: Settings | None = None) -> FastAPI:
    cfg = config or settings
    logging.basicConfig(level=cfg.log_level.upper())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = cfg
        app.state.store = store or build_store(
            cfg.graph_source, bundle_path=cfg.graph_bundle_path, buildings_path=cfg.buildings_path, dsn=cfg.database_url, build_dir=cfg.graph_build_dir,
        )
        app.state.tile_cache = tiles.TileCache(cfg.tile_cache_size)
        log.info("그래프 스토어 준비: %s", app.state.store.describe())
        yield

    app = FastAPI(
        title="Pathfinder Engine",
        description="교통약자 멀티모달 경로 탐색 엔진 (ACO + GA). 도보·지하철·버스 그래프에서 서로 다른 상위 3개 경로를 찾는다.",
        version="0.3.0",
        lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = (request.headers.get("X-Request-ID") or "").strip()[:64] or uuid.uuid4().hex
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/health", summary="헬스체크")
    def health(request: Request):
        store_obj: GraphStore | None = getattr(request.app.state, "store", None)
        if store_obj is None:
            raise HTTPException(status_code=503, detail="그래프 스토어가 준비되지 않았습니다.")
        try:
            graph = store_obj.describe()
        except Exception as exc:  # noqa: BLE001  — postgis 모드에서 DB 가 죽으면 503 으로 알린다
            raise HTTPException(status_code=503, detail=f"그래프 스토어 응답 없음: {type(exc).__name__}") from exc
        return {"status": "ok", "service": "engine", "graph": graph}

    @app.get("/api/snap", summary="좌표를 가장 가까운 보행 노드에 스냅")
    def snap(request: Request, lat: float = Query(..., ge=-90, le=90), lng: float = Query(..., ge=-180, le=180),
             max_distance_m: float = Query(300.0, ge=1, le=5000)):
        from .graph.store import SnapError

        try:
            p = request.app.state.store.nearest_walk_node(lat, lng, max_distance_m)
        except SnapError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"node_id": p.node_id, "lat": p.lat, "lng": p.lng, "distance_m": round(p.distance_m, 1)}

    return app


app = create_app()
