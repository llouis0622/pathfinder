"""엔진 설정 (환경변수)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    # file | postgis | postgis_memory
    graph_source: str = "file"
    graph_bundle_path: str = "../data/samples/grid_city.npz"
    buildings_path: str = "../data/samples/grid_city_buildings.json"
    database_url: str = "postgresql://pathfinder:pathfinder_dev@db:5432/pathfinder"
    engine_time_budget_s: float = 2.5
    aco_ants: int = 24
    aco_iterations: int = 60
    ga_generations: int = 25
    log_level: str = "INFO"


settings = Settings()
