from typing import Any

import httpx

from geolens_api.providers.contract import Citation, TokenUsage
from geolens_api.providers.http import (
    HTTPProvider,
    NormalizedProviderPayload,
    ProviderPayloadError,
)


class PerplexityProvider(HTTPProvider):
    """Perplexity Sonar adapter for web-grounded responses."""

    name = "perplexity"

    def __init__(
        self,
        *,
        model_identifier: str,
        api_key: str,
        client: httpx.AsyncClient,
        timeout_seconds: float,
        max_retries: int,
        retry_backoff_seconds: float,
        max_retry_after_seconds: float,
        base_url: str = "https://api.perplexity.ai",
    ) -> None:
        super().__init__(
            model_identifier=model_identifier,
            api_key=api_key,
            client=client,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
            max_retry_after_seconds=max_retry_after_seconds,
        )
        self._endpoint = f"{base_url.rstrip('/')}/v1/sonar"

    @property
    def endpoint(self) -> str:
        return self._endpoint

    def request_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def request_body(self, prompt: str) -> dict[str, Any]:
        return {
            "model": self.model_identifier,
            "messages": [{"role": "user", "content": prompt}],
        }

    def normalize_response(self, raw_response: dict[str, Any]) -> NormalizedProviderPayload:
        choices = raw_response.get("choices", [])
        choice = choices[0] if isinstance(choices, list) and choices else {}
        message = choice.get("message", {}) if isinstance(choice, dict) else {}
        response_text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(response_text, str):
            raise ProviderPayloadError("Perplexity response did not contain message content")

        usage = raw_response.get("usage", {})
        if not isinstance(usage, dict):
            usage = {}
        return NormalizedProviderPayload(
            response_text=response_text,
            citations=self._normalize_citations(raw_response),
            token_usage=TokenUsage(
                input_tokens=self._integer(usage.get("prompt_tokens")),
                output_tokens=self._integer(usage.get("completion_tokens")),
                total_tokens=self._integer(usage.get("total_tokens")),
                reasoning_tokens=self._optional_integer(usage.get("reasoning_tokens")),
            ),
            model_identifier=self._string_or_none(raw_response.get("model")),
        )

    @staticmethod
    def _normalize_citations(raw_response: dict[str, Any]) -> list[Citation]:
        citations: list[Citation] = []
        seen_urls: set[str] = set()
        search_results = raw_response.get("search_results", [])
        if isinstance(search_results, list):
            for result in search_results:
                if not isinstance(result, dict):
                    continue
                url = result.get("url")
                if not isinstance(url, str) or not url or url in seen_urls:
                    continue
                citations.append(
                    Citation(
                        url=url,
                        title=PerplexityProvider._string_or_none(result.get("title")),
                        cited_text=PerplexityProvider._string_or_none(result.get("snippet")),
                        published_at=PerplexityProvider._string_or_none(
                            result.get("date") or result.get("last_updated")
                        ),
                    )
                )
                seen_urls.add(url)

        raw_citations = raw_response.get("citations", [])
        if isinstance(raw_citations, list):
            for url in raw_citations:
                if isinstance(url, str) and url and url not in seen_urls:
                    citations.append(Citation(url=url))
                    seen_urls.add(url)
        return citations

    @staticmethod
    def _integer(value: object) -> int:
        return int(value) if isinstance(value, (int, float)) else 0

    @staticmethod
    def _optional_integer(value: object) -> int | None:
        return int(value) if isinstance(value, (int, float)) else None

    @staticmethod
    def _string_or_none(value: object) -> str | None:
        return value if isinstance(value, str) else None
