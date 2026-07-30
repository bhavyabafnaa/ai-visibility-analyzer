from pydantic import AnyUrl

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
