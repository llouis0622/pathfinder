"""백엔드 설정 (환경변수)."""
from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "change-me-in-production"
PLACEHOLDER_SECRETS = {DEFAULT_JWT_SECRET, "change-me-to-a-long-random-string", "ci-only-secret-0123456789abcdefghijklmnopqrstuv"}


def async_postgres_url(url: str) -> str:
    """루트 .env 하나를 엔진(psycopg)과 같이 쓰므로 `postgresql://` 도 받아 asyncpg 형식으로 맞춘다. SQLite 는 그대로."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql+psycopg://"):
        url = "postgresql://" + url[len("postgresql+psycopg://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


class Settings(BaseSettings):
    # 루트 .env(모든 서비스 공용) 를 먼저 읽고, backend/.env 가 있으면 그 값이 우선한다
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

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
    jwt_secret: str = DEFAULT_JWT_SECRET
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
    # ---- 관측성·캐시·제보 ----
    metrics_enabled: bool = True                          # /metrics (Prometheus)
    log_format: str = "text"                              # text | json
    search_cache_ttl_s: int = 600                         # 같은 출발·도착·프로필·시간대 검색 결과 재사용 (0 = 끔)
    search_cache_size: int = 500
    report_rate_limit_per_hour: int = 20                  # IP 당 시설 제보 한도
    # ---- 알림 (Slack 수신 웹훅 또는 JSON 웹훅). 관리자 화면에서 바꾼 값이 우선한다 ----
    alert_webhook_url: str = ""                           # 비어 있으면 알림 끔 (화면에서 넣을 수도 있음)
    alert_enabled: bool = True
    alert_interval_min: int = 5                           # 평가 주기

    @field_validator("database_url")
    @classmethod
    def _async_url(cls, v: str) -> str:
        return async_postgres_url(v)

    @property
    def jwt_secret_weak(self) -> bool:
        """자리표시자·짧은 비밀키. 이 상태에서는 관리자 기능을 끄고, 공개 주소에서는 로그인도 막는다."""
        return self.jwt_secret in PLACEHOLDER_SECRETS or len(self.jwt_secret) < 32

    @property
    def is_local(self) -> bool:
        return any(h in self.public_base_url for h in ("localhost", "127.0.0.1"))

    @property
    def cookie_secure_effective(self) -> bool:
        """COOKIE_SECURE 를 켜지 않아도 공개 주소가 https 면 Secure 쿠키를 쓴다."""
        return self.cookie_secure or self.public_base_url.startswith("https://")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
