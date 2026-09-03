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
    # ---- 로그인 (Kakao / Naver OAuth) ----
    public_base_url: str = "http://localhost:8000"        # OAuth redirect_uri 의 베이스 (이 백엔드의 공개 URL)
    frontend_url: str = "http://localhost:5173"           # 로그인 후 돌아갈 프론트 URL
    kakao_client_id: str = ""                             # Kakao Developers > 앱 키 > REST API 키
    kakao_client_secret: str = ""                         # 선택 (보안 > Client Secret)
    naver_client_id: str = ""
    naver_client_secret: str = ""
    jwt_secret: str = "change-me-in-production"
    session_days: int = 30
    cookie_secure: bool = False
    allow_dev_login: bool = False                         # true 면 /api/auth/dev/login 으로 데모 사용자 로그인 (로컬 전용)
    # ---- 개인화 (RL) ----
    personalization_enabled: bool = True
    personalization_epsilon: float = 0.1
    # ---- 관리자 ----
    admin_password: str = ""                              # 비어 있으면 관리자 기능 비활성 (/api/admin/* 404)
    admin_session_hours: int = 12
    admin_login_max_failures: int = 5                     # 이 횟수 실패하면 잠금
    admin_login_lockout_s: int = 300
    access_log_enabled: bool = True                       # 모든 /api 호출을 api_access_logs 에 기록
    log_retention_days: int = 90                          # 접근·장소검색·엔진 로그 보존 일수 (0 = 지우지 않음)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
