from functools import lru_cache
from pathlib import Path

from pydantic import Field, PositiveInt
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
    image_storage_root: Path = Field(
        default=Path("uploads"),
        validation_alias="IMAGE_STORAGE_ROOT",
    )
    max_upload_bytes: PositiveInt = Field(
        default=10 * 1024 * 1024,
        validation_alias="MAX_UPLOAD_BYTES",
    )
    max_image_pixels: PositiveInt = Field(
        default=40_000_000,
        validation_alias="MAX_IMAGE_PIXELS",
    )
    vision_provider: str = Field(default="gemini", validation_alias="VISION_PROVIDER")
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_vision_model: str = Field(
        default="gemini-2.5-flash",
        validation_alias="GEMINI_VISION_MODEL",
    )
    vision_timeout_seconds: PositiveInt = Field(
        default=30,
        validation_alias="VISION_TIMEOUT_SECONDS",
    )
    vision_low_confidence_threshold: float = Field(
        default=0.70,
        ge=0,
        le=1,
        validation_alias="VISION_LOW_CONFIDENCE_THRESHOLD",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
