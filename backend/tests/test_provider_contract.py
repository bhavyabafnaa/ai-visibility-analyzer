import pytest
from pydantic import ValidationError

from geolens_api.providers import (
    Citation,
    MockProvider,
    ProviderResponse,
    ProviderResponseStatus,
)


async def test_mock_provider_returns_recorded_fixture() -> None:
    provider = MockProvider(model_identifier="mock-v1")

    response = await provider.execute("What is GeoLens?")

    assert response.provider == "mock"
    assert response.model_identifier == "mock-v1"
    assert response.status is ProviderResponseStatus.SUCCEEDED
    assert response.citations == [
        Citation(
            url="https://example.test/geolens",
            title="GeoLens fixture",
            start_index=0,
            end_index=77,
            cited_text="GeoLens measures how brands appear in AI answers",
        )
    ]
    assert response.raw_response["fixture"] == "geolens-overview"
    assert response.token_usage.total_tokens == 20
    assert response.error is None


async def test_mock_provider_synthetic_response_is_deterministic() -> None:
    first_provider = MockProvider(model_identifier="mock-v1")
    second_provider = MockProvider(model_identifier="mock-v1")

    first = await first_provider.execute("An unrecorded prompt")
    second = await second_provider.execute("An unrecorded prompt")

    assert first == second
    assert first.raw_response["fixture"] == "synthetic"
    assert first.response_text.startswith("Deterministic mock response")


def test_provider_contract_requires_error_details_for_failure() -> None:
    with pytest.raises(ValidationError, match="require error information"):
        ProviderResponse(
            provider="mock",
            model_identifier="mock-v1",
            response_text="",
            latency_ms=0,
            status=ProviderResponseStatus.ERROR,
        )


def test_citation_rejects_reversed_text_range() -> None:
    with pytest.raises(ValidationError, match="must not precede"):
        Citation(url="https://example.test", start_index=5, end_index=4)
