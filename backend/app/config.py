"""백엔드 설정 (환경변수)."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    database_url: str = "postgresql+asyncpg://pathfinder:pathfinder_dev@db:5432/pathfinder"
    engine_url: str = "http://engine:8001"
    engine_timeout_s: float = 30.0
    # Kakao Developers REST API 키 (장소 검색). 없으면 로컬 역·정류장 색인만 사용
    kakao_rest_api_key: str = ""
    # open_meteo(키 불필요) | openweather | none
    weather_provider: str = "open_meteo"
    openweather_api_key: str = ""
    weather_cache_ttl_s: int = 300
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    data_dir: str = str(Path(__file__).resolve().parents[2] / "data")
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
