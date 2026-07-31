import pytest
from pydantic import AnyHttpUrl, AnyUrl, ValidationError
from pytest import MonkeyPatch

from geolens_api.config import Settings


def test_conventional_postgresql_url_uses_asyncpg_driver() -> None:
    settings = Settings(database_url=AnyUrl("postgresql://user:password@database:5432/geolens"))

    assert (
        settings.database_url_string == "postgresql+asyncpg://user:password@database:5432/geolens"
    )


def test_settings_accept_explicit_async_database_url() -> None:
    database_url = "postgresql+asyncpg://user:password@database:5432/geolens"

    settings = Settings(
        database_url=AnyUrl(database_url),
        debug=True,
        app_environment="test",
    )

    assert settings.database_url_string == database_url
    assert settings.debug is True
    assert settings.app_environment == "test"


def test_provider_models_and_limits_load_from_environment(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "openai-env-model")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-env-model")
    monkeypatch.setenv("PERPLEXITY_MODEL", "perplexity-env-model")
    monkeypatch.setenv("GEOLENS_PROVIDER_MAX_RETRIES", "4")

    settings = Settings()

    assert settings.openai_model == "openai-env-model"
    assert settings.gemini_model == "gemini-env-model"
    assert settings.perplexity_model == "perplexity-env-model"
    assert settings.provider_max_retries == 4


def test_production_rejects_plaintext_provider_endpoints() -> None:
    with pytest.raises(ValidationError, match="must use HTTPS"):
        Settings(
            app_environment="production",
            openai_base_url=AnyHttpUrl("http://provider.internal/v1"),
        )
