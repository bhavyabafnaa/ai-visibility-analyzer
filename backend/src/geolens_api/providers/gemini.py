from typing import Any

import httpx

from geolens_api.providers.contract import Citation, TokenUsage
from geolens_api.providers.http import (
    HTTPProvider,
    NormalizedProviderPayload,
    ProviderPayloadError,
)


class GeminiProvider(HTTPProvider):
    """Gemini Interactions adapter grounded with Google Search."""

    name = "gemini"

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
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
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
        self._endpoint = f"{base_url.rstrip('/')}/interactions"

    @property
    def endpoint(self) -> str:
        return self._endpoint

    def request_headers(self) -> dict[str, str]:
        return {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }

    def request_body(self, prompt: str) -> dict[str, Any]:
        return {
            "model": self.model_identifier,
            "input": prompt,
            "tools": [{"type": "google_search"}],
        }

    def normalize_response(self, raw_response: dict[str, Any]) -> NormalizedProviderPayload:
        if isinstance(raw_response.get("steps"), list):
            return self._normalize_interaction(raw_response)
        if isinstance(raw_response.get("candidates"), list):
            return self._normalize_generate_content(raw_response)
        raise ProviderPayloadError("Gemini response contained no interaction steps or candidates")

    def _normalize_interaction(
        self,
        raw_response: dict[str, Any],
    ) -> NormalizedProviderPayload:
        text_parts: list[str] = []
        citations: list[Citation] = []
        for step in raw_response.get("steps", []):
            if not isinstance(step, dict) or step.get("type") != "model_output":
                continue
            for content in step.get("content", []):
                if not isinstance(content, dict) or content.get("type") != "text":
                    continue
                text = content.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
                citations.extend(self._interaction_citations(content, text))

        if not text_parts:
            raise ProviderPayloadError("Gemini interaction did not contain output text")
        usage = self._usage(raw_response)
        return NormalizedProviderPayload(
            response_text="".join(text_parts),
            citations=citations,
            token_usage=usage,
            model_identifier=self._string_or_none(raw_response.get("model")),
        )

    def _normalize_generate_content(
        self,
        raw_response: dict[str, Any],
    ) -> NormalizedProviderPayload:
        candidates = raw_response.get("candidates", [])
        candidate = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
        content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
        parts = content.get("parts", []) if isinstance(content, dict) else []
        text = "".join(
            str(part["text"])
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
        if not text:
            raise ProviderPayloadError("Gemini candidate did not contain output text")
        return NormalizedProviderPayload(
            response_text=text,
            citations=self._grounding_citations(candidate, text),
            token_usage=self._usage(raw_response),
            model_identifier=self._string_or_none(
                raw_response.get("modelVersion") or raw_response.get("model")
            ),
        )

    @staticmethod
    def _interaction_citations(content: dict[str, Any], text: object) -> list[Citation]:
        annotations = content.get("annotations", [])
        if not isinstance(annotations, list):
            return []
        citations: list[Citation] = []
        for annotation in annotations:
            if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
                continue
            url = annotation.get("url")
            if not isinstance(url, str) or not url:
                continue
            start_index = GeminiProvider._optional_integer(annotation.get("start_index"))
            end_index = GeminiProvider._optional_integer(annotation.get("end_index"))
            cited_text = GeminiProvider._slice_text(text, start_index, end_index)
            citations.append(
                Citation(
                    url=url,
                    title=GeminiProvider._string_or_none(annotation.get("title")),
                    start_index=start_index,
                    end_index=end_index,
                    cited_text=cited_text,
                )
            )
        return citations

    @staticmethod
    def _grounding_citations(candidate: dict[str, Any], text: str) -> list[Citation]:
        metadata = candidate.get("groundingMetadata", {})
        if not isinstance(metadata, dict):
            return []
        chunks = metadata.get("groundingChunks", [])
        supports = metadata.get("groundingSupports", [])
        if not isinstance(chunks, list):
            return []

        citations: list[Citation] = []
        if isinstance(supports, list):
            for support in supports:
                if not isinstance(support, dict):
                    continue
                segment = support.get("segment", {})
                if not isinstance(segment, dict):
                    segment = {}
                start_index = GeminiProvider._optional_integer(segment.get("startIndex"))
                end_index = GeminiProvider._optional_integer(segment.get("endIndex"))
                cited_text = GeminiProvider._string_or_none(segment.get("text"))
                if cited_text is None:
                    cited_text = GeminiProvider._slice_text(text, start_index, end_index)
                indices = support.get("groundingChunkIndices", [])
                if not isinstance(indices, list):
                    continue
                for index in indices:
                    if not isinstance(index, int) or not 0 <= index < len(chunks):
                        continue
                    citation = GeminiProvider._citation_from_chunk(
                        chunks[index],
                        start_index=start_index,
                        end_index=end_index,
                        cited_text=cited_text,
                    )
                    if citation is not None:
                        citations.append(citation)

        if not citations:
            for chunk in chunks:
                citation = GeminiProvider._citation_from_chunk(chunk)
                if citation is not None:
                    citations.append(citation)
        return citations

    @staticmethod
    def _citation_from_chunk(
        chunk: object,
        *,
        start_index: int | None = None,
        end_index: int | None = None,
        cited_text: str | None = None,
    ) -> Citation | None:
        if not isinstance(chunk, dict):
            return None
        web = chunk.get("web", {})
        if not isinstance(web, dict):
            return None
        url = web.get("uri")
        if not isinstance(url, str) or not url:
            return None
        return Citation(
            url=url,
            title=GeminiProvider._string_or_none(web.get("title")),
            start_index=start_index,
            end_index=end_index,
            cited_text=cited_text,
        )

    @staticmethod
    def _usage(raw_response: dict[str, Any]) -> TokenUsage:
        usage = raw_response.get("usage") or raw_response.get("usageMetadata") or {}
        if not isinstance(usage, dict):
            usage = {}
        input_tokens = GeminiProvider._integer(
            usage.get("input_tokens") or usage.get("promptTokenCount")
        )
        output_tokens = GeminiProvider._integer(
            usage.get("output_tokens") or usage.get("candidatesTokenCount")
        )
        total_tokens = GeminiProvider._integer(
            usage.get("total_tokens") or usage.get("totalTokenCount")
        )
        if total_tokens == 0:
            total_tokens = input_tokens + output_tokens
        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cached_tokens=GeminiProvider._optional_integer(
                usage.get("cached_tokens") or usage.get("cachedContentTokenCount")
            ),
            reasoning_tokens=GeminiProvider._optional_integer(
                usage.get("reasoning_tokens") or usage.get("thoughtsTokenCount")
            ),
        )

    @staticmethod
    def _slice_text(text: object, start_index: int | None, end_index: int | None) -> str | None:
        if (
            isinstance(text, str)
            and start_index is not None
            and end_index is not None
            and start_index <= end_index <= len(text)
        ):
            return text[start_index:end_index]
        return None

    @staticmethod
    def _integer(value: object) -> int:
        return int(value) if isinstance(value, (int, float)) else 0

    @staticmethod
    def _optional_integer(value: object) -> int | None:
        return int(value) if isinstance(value, (int, float)) else None

    @staticmethod
    def _string_or_none(value: object) -> str | None:
        return value if isinstance(value, str) else None
