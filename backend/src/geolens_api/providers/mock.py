from hashlib import sha256

from pydantic import BaseModel, Field

from geolens_api.providers.contract import (
    Citation,
    ProviderResponse,
    ProviderResponseStatus,
    TokenUsage,
)


class MockFixture(BaseModel):
    """A deterministic response used by local development and contract tests."""

    response_text: str
    citations: list[Citation] = Field(default_factory=list)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    raw_response: dict[str, object] = Field(default_factory=dict)
    latency_ms: float = Field(default=1.0, ge=0)


DEFAULT_MOCK_FIXTURES: dict[str, MockFixture] = {
    "What is GeoLens?": MockFixture(
        response_text=(
            "GeoLens measures how brands appear in AI answers and which web sources are cited."
        ),
        citations=[
            Citation(
                url="https://example.test/geolens",
                title="GeoLens fixture",
                start_index=0,
                end_index=77,
                cited_text="GeoLens measures how brands appear in AI answers",
            )
        ],
        token_usage=TokenUsage(input_tokens=5, output_tokens=15, total_tokens=20),
        raw_response={
            "fixture": "geolens-overview",
            "answer": (
                "GeoLens measures how brands appear in AI answers and which web sources are cited."
            ),
        },
        latency_ms=1.0,
    )
}


class MockProvider:
    """Backend-only deterministic provider with no network dependency."""

    name = "mock"

    def __init__(
        self,
        *,
        model_identifier: str,
        fixtures: dict[str, MockFixture] | None = None,
    ) -> None:
        self._model_identifier = model_identifier
        self._fixtures = fixtures or DEFAULT_MOCK_FIXTURES

    @property
    def model_identifier(self) -> str:
        return self._model_identifier

    @property
    def enabled(self) -> bool:
        return True

    @property
    def disabled_reason(self) -> None:
        return None

    async def execute(self, prompt: str) -> ProviderResponse:
        fixture = self._fixtures.get(prompt)
        if fixture is None:
            fixture = self._synthetic_fixture(prompt)
        return ProviderResponse(
            provider=self.name,
            model_identifier=self.model_identifier,
            response_text=fixture.response_text,
            citations=fixture.citations,
            raw_response=fixture.raw_response,
            token_usage=fixture.token_usage,
            latency_ms=fixture.latency_ms,
            status=ProviderResponseStatus.SUCCEEDED,
        )

    def _synthetic_fixture(self, prompt: str) -> MockFixture:
        digest = sha256(prompt.encode("utf-8")).hexdigest()
        response_text = f"Deterministic mock response {digest[:12]} for: {prompt}"
        input_tokens = len(prompt.split())
        output_tokens = len(response_text.split())
        return MockFixture(
            response_text=response_text,
            citations=[
                Citation(
                    url=f"https://example.test/mock/{digest[:16]}",
                    title=f"Mock source {digest[:8]}",
                )
            ],
            raw_response={
                "fixture": "synthetic",
                "prompt_sha256": digest,
                "answer": response_text,
            },
            token_usage=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
            latency_ms=1.0,
        )
