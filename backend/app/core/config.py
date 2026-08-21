from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(
        default="FlyRank Image Relevance API",
        validation_alias="APP_NAME",
    )
    app_environment: str = Field(
        default="development",
        validation_alias="APP_ENV",
    )
    database_url: str = Field(
        default="postgresql+psycopg://flyrank:flyrank@localhost:5432/flyrank",
        validation_alias="DATABASE_URL",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

