import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from geolens_api.providers import (
    GeminiProvider,
    OpenAIProvider,
    PerplexityProvider,
    ProviderResponse,
    ProviderResponseStatus,
)
from geolens_api.providers.http import HTTPProvider

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "providers"
ProviderFactory = Callable[[httpx.AsyncClient], HTTPProvider]


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIRECTORY / name).read_text(encoding="utf-8"))


def provider_kwargs(client: httpx.AsyncClient) -> dict[str, object]:
    return {
        "api_key": "test-key",
        "client": client,
        "timeout_seconds": 1.0,
        "max_retries": 0,
        "retry_backoff_seconds": 0.0,
        "max_retry_after_seconds": 0.0,
    }


async def execute_fixture(
    factory: ProviderFactory,
    payload: dict[str, Any],
) -> tuple[httpx.Request, ProviderResponse]:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await factory(client).execute("Measure GeoLens visibility")
    assert captured_request is not None
    return captured_request, response


async def test_openai_adapter_normalizes_responses_fixture() -> None:
    request, result = await execute_fixture(
        lambda client: OpenAIProvider(
            model_identifier="configured-openai-model",
            **provider_kwargs(client),  # type: ignore[arg-type]
        ),
        load_fixture("openai_response.json"),
    )

    assert result.status is ProviderResponseStatus.SUCCEEDED
    assert result.provider == "openai"
    assert result.model_identifier == "gpt-fixture"
    assert result.response_text == "GeoLens tracks brand visibility."
    assert result.citations[0].url == "https://example.com/openai-source"
    assert result.citations[0].cited_text == "GeoLens tracks"
    assert result.token_usage.model_dump() == {
        "input_tokens": 10,
        "output_tokens": 7,
        "total_tokens": 17,
        "cached_tokens": 2,
        "reasoning_tokens": 1,
    }
    assert result.raw_response == load_fixture("openai_response.json")
    assert request.url.path == "/v1/responses"
    assert json.loads(request.content)["tools"] == [{"type": "web_search"}]


async def test_gemini_adapter_normalizes_interactions_fixture() -> None:
    request, result = await execute_fixture(
        lambda client: GeminiProvider(
            model_identifier="configured-gemini-model",
            **provider_kwargs(client),  # type: ignore[arg-type]
        ),
        load_fixture("gemini_response.json"),
    )

    assert result.status is ProviderResponseStatus.SUCCEEDED
    assert result.provider == "gemini"
    assert result.model_identifier == "gemini-fixture"
    assert result.response_text == "GeoLens measures AI visibility."
    assert result.citations[0].url == "https://example.com/gemini-source"
    assert result.citations[0].cited_text == "GeoLens measur"
    assert result.token_usage.total_tokens == 17
    assert request.url.path == "/v1beta/interactions"
    assert json.loads(request.content)["tools"] == [{"type": "google_search"}]


async def test_gemini_adapter_accepts_recorded_generate_content_shape() -> None:
    _, result = await execute_fixture(
        lambda client: GeminiProvider(
            model_identifier="configured-gemini-model",
            **provider_kwargs(client),  # type: ignore[arg-type]
        ),
        load_fixture("gemini_generate_content_response.json"),
    )

    assert result.status is ProviderResponseStatus.SUCCEEDED
    assert result.model_identifier == "gemini-legacy-fixture"
    assert result.citations[0].url == "https://example.com/gemini-legacy-source"
    assert result.citations[0].start_index == 0
    assert result.citations[0].end_index == 14


async def test_perplexity_adapter_normalizes_sonar_fixture() -> None:
    request, result = await execute_fixture(
        lambda client: PerplexityProvider(
            model_identifier="configured-sonar-model",
            **provider_kwargs(client),  # type: ignore[arg-type]
        ),
        load_fixture("perplexity_response.json"),
    )

    assert result.status is ProviderResponseStatus.SUCCEEDED
    assert result.provider == "perplexity"
    assert result.model_identifier == "sonar-fixture"
    assert [citation.url for citation in result.citations] == [
        "https://example.com/perplexity-source",
        "https://example.com/citation-only",
    ]
    assert result.citations[0].title == "Perplexity fixture source"
    assert result.token_usage.reasoning_tokens == 2
    assert request.url.path == "/v1/sonar"


async def test_adapter_retries_rate_limit_and_honors_retry_after() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0.25"},
                json={"error": {"code": "rate_limit", "message": "Slow down"}},
            )
        return httpx.Response(200, json=load_fixture("openai_response.json"))

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAIProvider(
            model_identifier="configured-openai-model",
            api_key="test-key",
            client=client,
            timeout_seconds=1,
            max_retries=1,
            retry_backoff_seconds=0,
            max_retry_after_seconds=1,
        )
        provider._sleep = record_sleep
        result = await provider.execute("Measure GeoLens visibility")

    assert result.status is ProviderResponseStatus.SUCCEEDED
    assert attempts == 2
    assert delays == [0.25]


async def test_rate_limit_exhaustion_is_explicit_and_retains_raw_json() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"code": "rate_limit", "message": "Quota exhausted"}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = PerplexityProvider(
            model_identifier="sonar-test",
            **provider_kwargs(client),  # type: ignore[arg-type]
        )
        result = await provider.execute("Measure GeoLens visibility")

    assert result.status is ProviderResponseStatus.RATE_LIMITED
    assert result.error is not None
    assert result.error.code == "rate_limit"
    assert result.error.http_status == 429
    assert result.raw_response == {"error": {"code": "rate_limit", "message": "Quota exhausted"}}


async def test_timeout_exhaustion_is_explicit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiProvider(
            model_identifier="gemini-test",
            **provider_kwargs(client),  # type: ignore[arg-type]
        )
        result = await provider.execute("Measure GeoLens visibility")

    assert result.status is ProviderResponseStatus.TIMED_OUT
    assert result.error is not None
    assert result.error.code == "timeout"
    assert result.error.retryable is True


@pytest.mark.parametrize(
    ("factory", "fixture_name"),
    [
        (
            lambda client: OpenAIProvider(
                model_identifier="openai-live",
                **provider_kwargs(client),  # type: ignore[arg-type]
            ),
            "openai_response.json",
        ),
        (
            lambda client: GeminiProvider(
                model_identifier="gemini-live",
                **provider_kwargs(client),  # type: ignore[arg-type]
            ),
            "gemini_response.json",
        ),
        (
            lambda client: PerplexityProvider(
                model_identifier="perplexity-live",
                **provider_kwargs(client),  # type: ignore[arg-type]
            ),
            "perplexity_response.json",
        ),
    ],
)
async def test_all_adapters_satisfy_common_contract(
    factory: ProviderFactory,
    fixture_name: str,
) -> None:
    _, result = await execute_fixture(factory, load_fixture(fixture_name))

    assert result.status is ProviderResponseStatus.SUCCEEDED
    assert result.response_text
    assert result.citations
    assert result.raw_response
    assert result.token_usage.total_tokens > 0
    assert result.latency_ms >= 0
    assert result.error is None
