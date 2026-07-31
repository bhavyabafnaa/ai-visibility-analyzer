from typing import Any

import httpx

from geolens_api.providers.contract import Citation, TokenUsage
from geolens_api.providers.http import (
    HTTPProvider,
    NormalizedProviderPayload,
    ProviderPayloadError,
)


class OpenAIProvider(HTTPProvider):
    """OpenAI Responses API adapter with hosted web search."""

    name = "openai"

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
        base_url: str = "https://api.openai.com/v1",
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
        self._endpoint = f"{base_url.rstrip('/')}/responses"

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
            "input": prompt,
            "tools": [{"type": "web_search"}],
            "include": ["web_search_call.action.sources"],
            "store": False,
        }

    def normalize_response(self, raw_response: dict[str, Any]) -> NormalizedProviderPayload:
        text_parts: list[str] = []
        citations: list[Citation] = []
        text_offset = 0

        for output_item in raw_response.get("output", []):
            if not isinstance(output_item, dict) or output_item.get("type") != "message":
                continue
            for content in output_item.get("content", []):
                if not isinstance(content, dict) or content.get("type") != "output_text":
                    continue
                text = content.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
                citations.extend(
                    self._normalize_annotations(
                        content.get("annotations", []),
                        text,
                        text_offset=text_offset,
                    )
                )
                if isinstance(text, str):
                    text_offset += len(text)

        if not text_parts:
            raise ProviderPayloadError("OpenAI response did not contain output text")

        usage = raw_response.get("usage", {})
        if not isinstance(usage, dict):
            usage = {}
        input_details = usage.get("input_tokens_details", {})
        output_details = usage.get("output_tokens_details", {})
        if not isinstance(input_details, dict):
            input_details = {}
        if not isinstance(output_details, dict):
            output_details = {}

        return NormalizedProviderPayload(
            response_text="".join(text_parts),
            citations=citations,
            token_usage=TokenUsage(
                input_tokens=self._integer(usage.get("input_tokens")),
                output_tokens=self._integer(usage.get("output_tokens")),
                total_tokens=self._integer(usage.get("total_tokens")),
                cached_tokens=self._optional_integer(input_details.get("cached_tokens")),
                reasoning_tokens=self._optional_integer(output_details.get("reasoning_tokens")),
            ),
            model_identifier=self._string_or_none(raw_response.get("model")),
        )

    @staticmethod
    def _normalize_annotations(
        annotations: object,
        text: object,
        *,
        text_offset: int = 0,
    ) -> list[Citation]:
        if not isinstance(annotations, list):
            return []
        normalized: list[Citation] = []
        for annotation in annotations:
            if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
                continue
            citation_data = annotation.get("url_citation", annotation)
            if not isinstance(citation_data, dict):
                continue
            url = citation_data.get("url")
            if not isinstance(url, str) or not url:
                continue
            start_index = OpenAIProvider._optional_integer(citation_data.get("start_index"))
            end_index = OpenAIProvider._optional_integer(citation_data.get("end_index"))
            cited_text = None
            if (
                isinstance(text, str)
                and start_index is not None
                and end_index is not None
                and start_index <= end_index <= len(text)
            ):
                cited_text = text[start_index:end_index]
            normalized.append(
                Citation(
                    url=url,
                    title=OpenAIProvider._string_or_none(citation_data.get("title")),
                    start_index=(start_index + text_offset if start_index is not None else None),
                    end_index=end_index + text_offset if end_index is not None else None,
                    cited_text=cited_text,
                )
            )
        return normalized

    @staticmethod
    def _integer(value: object) -> int:
        return int(value) if isinstance(value, (int, float)) else 0

    @staticmethod
    def _optional_integer(value: object) -> int | None:
        return int(value) if isinstance(value, (int, float)) else None

    @staticmethod
    def _string_or_none(value: object) -> str | None:
        return value if isinstance(value, str) else None
