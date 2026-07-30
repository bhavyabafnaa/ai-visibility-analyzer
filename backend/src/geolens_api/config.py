from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, AnyUrl, Field, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="GEOLENS_",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "GeoLens API"
    app_environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    database_url: AnyUrl = Field(
        default=AnyUrl("postgresql+asyncpg://geolens:geolens_dev_password@localhost:5432/geolens"),
        validation_alias=AliasChoices("DATABASE_URL", "GEOLENS_DATABASE_URL"),
    )
    redis_url: RedisDsn = Field(
        default=RedisDsn("redis://localhost:6379/0"),
        validation_alias=AliasChoices("REDIS_URL", "GEOLENS_REDIS_URL"),
    )
    crawler_page_limit: int = Field(default=100, ge=1, le=10_000)
    crawler_max_depth: int = Field(default=3, ge=0, le=50)
    crawler_max_response_bytes: int = Field(default=2_000_000, ge=1_024, le=100_000_000)
    crawler_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    crawler_concurrency: int = Field(default=5, ge=1, le=50)
    crawler_max_redirects: int = Field(default=5, ge=0, le=20)
    crawler_sitemap_limit: int = Field(default=20, ge=1, le=100)
    crawler_renderer_min_text_characters: int = Field(default=80, ge=0, le=10_000)
    crawler_user_agent: str = Field(default="GeoLensBot/0.1", min_length=1, max_length=200)

    @field_validator("database_url", mode="before")
    @classmethod
    def use_async_postgresql_driver(cls, value: object) -> object:
        """Translate conventional PostgreSQL URLs to SQLAlchemy's async driver."""
        if not isinstance(value, (str, AnyUrl)):
            return value
        url = str(value)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @property
    def database_url_string(self) -> str:
        return str(self.database_url)

    @property
    def redis_url_string(self) -> str:
        return str(self.redis_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
