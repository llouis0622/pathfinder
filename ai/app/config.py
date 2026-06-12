from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    backend_url: str = "http://backend:8000"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
