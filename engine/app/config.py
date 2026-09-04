"""엔진 설정 (환경변수)."""
from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def plain_postgres_url(url: str) -> str:
    """루트 .env 하나를 백엔드(asyncpg)와 같이 쓰므로 `postgresql+asyncpg://` 도 받아 psycopg 형식으로 맞춘다."""
    return url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg://", "postgresql://").replace("postgres://", "postgresql://")


class Settings(BaseSettings):
    # 루트 .env(모든 서비스 공용) 를 먼저 읽고, engine/.env 가 있으면 그 값이 우선한다
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_env: str = "dev"
    # auto | file | postgis | postgis_memory
    #   auto: PostGIS 에 그래프가 있으면 postgis_memory → 없으면 GRAPH_BUILD_DIR 의 번들 → 없으면 샘플 격자 도시
    graph_source: str = "auto"
    graph_bundle_path: str = "../data/samples/grid_city.npz"
    buildings_path: str = "../data/samples/grid_city_buildings.json"
    graph_build_dir: str = "../data/build"                 # run_all 산출물 (graph_bundle.npz, buildings.json)
    database_url: str = "postgresql://pathfinder:pathfinder_dev@db:5432/pathfinder"
    engine_time_budget_s: float = 2.5
    aco_ants: int = 24
    aco_iterations: int = 60
    ga_generations: int = 25
    log_level: str = "INFO"
    tile_cache_size: int = 4096          # 타일 LRU 항목 수 (0 이면 캐시 끔)

    @field_validator("database_url")
    @classmethod
    def _plain(cls, v: str) -> str:
        return plain_postgres_url(v)


settings = Settings()
