from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "LessonLink API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://lessonlink:lessonlink@localhost:5432/lessonlink"

    jwt_secret: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 12

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174"]

    line_login_channel_id: str = ""
    line_login_channel_secret: str = ""
    line_mock_enabled: bool = False
    line_messaging_channel_id: str = ""
    line_messaging_channel_secret: str = ""
    line_messaging_channel_access_token: str = ""
    liff_id: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
