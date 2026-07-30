from pydantic import SecretStr

from geolens_api.config import Settings
from geolens_api.providers import (
    ProviderRegistry,
    ProviderResponseStatus,
    UnknownProviderError,
)


async def test_missing_credentials_disable_each_live_provider() -> None:
    registry = ProviderRegistry.from_settings(
        Settings(
            openai_api_key=None,
            gemini_api_key=None,
            perplexity_api_key=None,
        )
    )

    availability = {item.name: item for item in registry.availability()}

    assert availability["mock"].enabled is True
    assert availability["openai"].disabled_reason == "OPENAI_API_KEY is not configured"
    assert availability["gemini"].disabled_reason == "GEMINI_API_KEY is not configured"
    assert availability["perplexity"].disabled_reason == "PERPLEXITY_API_KEY is not configured"
    await registry.aclose()


async def test_disabled_provider_does_not_fall_back_to_mock() -> None:
    registry = ProviderRegistry.from_settings(Settings(openai_api_key=None))

    result = await registry.get("openai").execute("What is GeoLens?")

    assert result.provider == "openai"
    assert result.status is ProviderResponseStatus.DISABLED
    assert result.error is not None
    assert result.error.code == "provider_disabled"
    assert result.raw_response == {"disabled_reason": "OPENAI_API_KEY is not configured"}
    await registry.aclose()


async def test_configured_credential_enables_exact_provider() -> None:
    registry = ProviderRegistry.from_settings(
        Settings(
            openai_api_key=SecretStr("test-openai-key"),
            openai_model="openai-env-model",
            gemini_api_key=None,
            perplexity_api_key=None,
        )
    )

    availability = {item.name: item for item in registry.availability()}

    assert availability["openai"].enabled is True
    assert availability["openai"].model_identifier == "openai-env-model"
    assert availability["gemini"].enabled is False
    await registry.aclose()


def test_unknown_provider_is_rejected_instead_of_falling_back() -> None:
    registry = ProviderRegistry.from_settings(Settings())

    try:
        registry.get("not-a-provider")
    except UnknownProviderError as error:
        assert str(error) == "Unknown provider: not-a-provider"
    else:
        raise AssertionError("unknown provider should have raised")
