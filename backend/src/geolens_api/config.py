from functools import lru_cache
from typing import Literal

from pydantic import (
    AliasChoices,
    AnyHttpUrl,
    AnyUrl,
    Field,
    RedisDsn,
    SecretStr,
    field_validator,
    model_validator,
)
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
    mock_model: str = Field(
        default="mock-v1",
        min_length=1,
        validation_alias=AliasChoices("GEOLENS_MOCK_MODEL", "MOCK_MODEL"),
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "GEOLENS_OPENAI_API_KEY"),
    )
    openai_model: str | None = Field(
        default=None,
        min_length=1,
        validation_alias=AliasChoices("OPENAI_MODEL", "GEOLENS_OPENAI_MODEL"),
    )
    openai_base_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("https://api.openai.com/v1"),
        validation_alias=AliasChoices("OPENAI_BASE_URL", "GEOLENS_OPENAI_BASE_URL"),
    )
    gemini_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "GEOLENS_GEMINI_API_KEY"),
    )
    gemini_model: str | None = Field(
        default=None,
        min_length=1,
        validation_alias=AliasChoices("GEMINI_MODEL", "GEOLENS_GEMINI_MODEL"),
    )
    gemini_base_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("https://generativelanguage.googleapis.com/v1beta"),
        validation_alias=AliasChoices("GEMINI_BASE_URL", "GEOLENS_GEMINI_BASE_URL"),
    )
    perplexity_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("PERPLEXITY_API_KEY", "GEOLENS_PERPLEXITY_API_KEY"),
    )
    perplexity_model: str | None = Field(
        default=None,
        min_length=1,
        validation_alias=AliasChoices("PERPLEXITY_MODEL", "GEOLENS_PERPLEXITY_MODEL"),
    )
    perplexity_base_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("https://api.perplexity.ai"),
        validation_alias=AliasChoices(
            "PERPLEXITY_BASE_URL",
            "GEOLENS_PERPLEXITY_BASE_URL",
        ),
    )
    provider_timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    provider_max_retries: int = Field(default=2, ge=0, le=10)
    provider_retry_backoff_seconds: float = Field(default=0.5, ge=0, le=60)
    provider_max_retry_after_seconds: float = Field(default=30.0, ge=0, le=300)

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

    @field_validator("openai_model", "gemini_model", "perplexity_model", mode="before")
    @classmethod
    def normalize_optional_provider_models(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @model_validator(mode="after")
    def require_models_for_configured_provider_credentials(self) -> "Settings":
        missing = [
            model_name
            for model_name, credential, model in (
                ("OPENAI_MODEL", self.openai_api_key, self.openai_model),
                ("GEMINI_MODEL", self.gemini_api_key, self.gemini_model),
                ("PERPLEXITY_MODEL", self.perplexity_api_key, self.perplexity_model),
            )
            if self._has_credential(credential) and model is None
        ]
        if missing:
            raise ValueError(
                "provider model identifiers are required when credentials are configured: "
                + ", ".join(missing)
            )
        return self

    @model_validator(mode="after")
    def require_secure_production_provider_endpoints(self) -> "Settings":
        if self.app_environment != "production":
            return self
        insecure = [
            name
            for name, url in (
                ("OPENAI_BASE_URL", self.openai_base_url),
                ("GEMINI_BASE_URL", self.gemini_base_url),
                ("PERPLEXITY_BASE_URL", self.perplexity_base_url),
            )
            if url.scheme != "https"
        ]
        if insecure:
            raise ValueError("production provider base URLs must use HTTPS: " + ", ".join(insecure))
        return self

    @staticmethod
    def _has_credential(secret: SecretStr | None) -> bool:
        return secret is not None and bool(secret.get_secret_value().strip())

    @property
    def database_url_string(self) -> str:
        return str(self.database_url)

    @property
    def redis_url_string(self) -> str:
        return str(self.redis_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
