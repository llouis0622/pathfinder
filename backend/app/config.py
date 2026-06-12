from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 데이터베이스 연결 URL
    database_url: str = "postgresql+asyncpg://pathfinder:pathfinder_dev@db:5432/pathfinder"
    # AI 서버 URL
    ai_server_url: str = "http://ai:8001"
    # 카카오 REST API 키 (장소 검색용)
    kakao_rest_api_key: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
