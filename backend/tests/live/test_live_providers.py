import os

import pytest

from geolens_api.config import Settings
from geolens_api.providers import ProviderRegistry, ProviderResponseStatus

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(bool(os.getenv("CI")), reason="live provider tests are disabled in CI"),
    pytest.mark.skipif(
        os.getenv("GEOLENS_RUN_LIVE_PROVIDER_TESTS") != "1",
        reason="set GEOLENS_RUN_LIVE_PROVIDER_TESTS=1 to enable live provider tests",
    ),
]


@pytest.mark.parametrize("provider_name", ["openai", "gemini", "perplexity"])
async def test_live_provider_contract(provider_name: str) -> None:
    registry = ProviderRegistry.from_settings(Settings())
    provider = registry.get(provider_name)
    if not provider.enabled:
        await registry.aclose()
        pytest.skip(provider.disabled_reason or f"{provider_name} is disabled")

    result = await provider.execute("What is one positive technology news story from today?")
    await registry.aclose()

    assert result.status is ProviderResponseStatus.SUCCEEDED
    assert result.response_text
    assert result.raw_response
    assert result.model_identifier
