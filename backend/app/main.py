"""Pathfinder 백엔드 FastAPI 앱: 장소 검색, 날씨, 경로 오케스트레이션, 로그."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from . import audit, observability
from .admin_routers import guarded as admin_guarded
from .admin_routers import router as admin_router
from .config import Settings, settings
from .database import Database
from .reports import router as reports_router
from .routers import router
from .services import engine_client
from .services.cache import SearchCache
from .services.maintenance import start_retention

log = logging.getLogger("backend")


def create_app(config: Settings | None = None) -> FastAPI:
    cfg = config or settings
    observability.configure_logging(cfg.log_level, cfg.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = cfg
        app.state.db = Database(cfg.database_url)
        app.state.search_cache = SearchCache(cfg.search_cache_ttl_s, cfg.search_cache_size)
        await app.state.db.create_all()
        log.info("DB 준비 (%s)", cfg.database_url.split("@")[-1])
        retention = start_retention(app)
        yield
        if retention is not None:
            retention.cancel()
        await app.state.db.dispose()

    app = FastAPI(title="Pathfinder Backend", description="교통약자 맞춤형 경로 추천 서비스 백엔드 API", version="0.4.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=cfg.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)
    app.include_router(admin_router)
    app.include_router(admin_guarded)
    app.include_router(reports_router)
    audit.install(app)
    observability.install(app, cfg.metrics_enabled)   # 가장 바깥: 요청 ID 를 먼저 만들고 접근 로그가 쓴다

    @app.get("/health", summary="헬스체크 (엔진 상태 포함)")
    async def health(request: Request):
        engine = await engine_client.health(request.app.state.settings)
        observability.ENGINE_UP.set(1 if engine.get("status") == "ok" else 0)
        return {"status": "ok", "service": "backend", "engine": engine, "request_id": getattr(request.state, "request_id", "")}

    return app


app = create_app()
