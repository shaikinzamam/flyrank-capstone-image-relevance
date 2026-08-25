from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, PositiveInt, field_validator, model_validator
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
    cors_allowed_origins: str = Field(
        default="http://localhost:3000",
        validation_alias="CORS_ALLOWED_ORIGINS",
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
    vision_budget_usd: float | None = Field(
        default=None,
        ge=0,
        validation_alias="VISION_BUDGET_USD",
    )
    vision_estimated_cost_per_call_usd: float | None = Field(
        default=None,
        ge=0,
        validation_alias="VISION_ESTIMATED_COST_PER_CALL_USD",
    )
    processing_max_attempts: PositiveInt = Field(
        default=3,
        validation_alias="PROCESSING_MAX_ATTEMPTS",
    )
    processing_initial_backoff_seconds: PositiveInt = Field(
        default=5,
        validation_alias="PROCESSING_INITIAL_BACKOFF_SECONDS",
    )
    processing_max_backoff_seconds: PositiveInt = Field(
        default=300,
        validation_alias="PROCESSING_MAX_BACKOFF_SECONDS",
    )
    processing_lease_seconds: PositiveInt = Field(
        default=60,
        validation_alias="PROCESSING_LEASE_SECONDS",
    )
    worker_poll_seconds: float = Field(
        default=1.0,
        gt=0,
        validation_alias="WORKER_POLL_SECONDS",
    )
    embedding_provider: str = Field(
        default="local", validation_alias="EMBEDDING_PROVIDER"
    )
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        validation_alias="EMBEDDING_MODEL",
    )
    embedding_version: str = Field(
        default="c9745ed1d9f207416be6d2e6f8de32d1f16199bf",
        validation_alias="EMBEDDING_VERSION",
    )
    embedding_dimensions: PositiveInt = Field(
        default=384, validation_alias="EMBEDDING_DIMENSIONS"
    )
    embedding_normalize: bool = Field(
        default=True, validation_alias="EMBEDDING_NORMALIZE"
    )
    evaluation_dataset_path: Path = Field(
        default=Path("../data/evaluation.jsonl"),
        validation_alias="EVALUATION_DATASET_PATH",
    )

    @field_validator(
        "vision_budget_usd",
        "vision_estimated_cost_per_call_usd",
        mode="before",
    )
    @classmethod
    def empty_optional_numbers_are_unset(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip().rstrip("/") for origin in value.split(",")]
        if not origins or any(not origin or origin == "*" for origin in origins):
            raise ValueError("CORS_ALLOWED_ORIGINS must list explicit origins")
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "CORS_ALLOWED_ORIGINS entries must be HTTP(S) origins"
                )
        return ",".join(origins)

    @model_validator(mode="after")
    def validate_worker_configuration(self) -> "Settings":
        if (
            self.processing_initial_backoff_seconds
            > self.processing_max_backoff_seconds
        ):
            raise ValueError(
                "PROCESSING_INITIAL_BACKOFF_SECONDS cannot exceed "
                "PROCESSING_MAX_BACKOFF_SECONDS"
            )
        if self.processing_lease_seconds <= self.vision_timeout_seconds:
            raise ValueError(
                "PROCESSING_LEASE_SECONDS must exceed VISION_TIMEOUT_SECONDS"
            )
        if self.embedding_dimensions != 384:
            raise ValueError(
                "EMBEDDING_DIMENSIONS must be 384 to match the pgvector schema"
            )
        if not self.embedding_normalize:
            raise ValueError("EMBEDDING_NORMALIZE must remain enabled")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
