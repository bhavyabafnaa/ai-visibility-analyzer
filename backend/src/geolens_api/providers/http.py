import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from email.utils import parsedate_to_datetime
from time import perf_counter, time
from typing import Any

import httpx
from pydantic import BaseModel, Field

from geolens_api.providers.contract import (
    Citation,
    ProviderError,
    ProviderResponse,
    ProviderResponseStatus,
    TokenUsage,
)

TRANSIENT_HTTP_STATUSES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


class NormalizedProviderPayload(BaseModel):
    response_text: str
    citations: list[Citation] = Field(default_factory=list)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    model_identifier: str | None = None


class ProviderPayloadError(ValueError):
    """Raised when a successful HTTP payload does not match the provider contract."""


class HTTPProvider(ABC):
    """Shared timeout, retry, and error behavior for HTTP provider adapters."""

    name: str

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
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        self._model_identifier = model_identifier
        self._api_key = api_key
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._max_retry_after_seconds = max_retry_after_seconds
        self._sleep = sleep

    @property
    def model_identifier(self) -> str:
        return self._model_identifier

    @property
    def enabled(self) -> bool:
        return True

    @property
    def disabled_reason(self) -> None:
        return None

    @property
    @abstractmethod
    def endpoint(self) -> str: ...

    @abstractmethod
    def request_headers(self) -> dict[str, str]: ...

    @abstractmethod
    def request_body(self, prompt: str) -> dict[str, Any]: ...

    @abstractmethod
    def normalize_response(self, raw_response: dict[str, Any]) -> NormalizedProviderPayload: ...

    async def execute(self, prompt: str) -> ProviderResponse:
        started_at = perf_counter()
        raw_response: dict[str, Any] = {}
        attempts = 0

        while attempts <= self._max_retries:
            attempts += 1
            try:
                response = await self._client.post(
                    self.endpoint,
                    headers=self.request_headers(),
                    json=self.request_body(prompt),
                    timeout=self._timeout_seconds,
                )
            except httpx.TimeoutException as error:
                if attempts <= self._max_retries:
                    await self._sleep(self._backoff_delay(attempts))
                    continue
                return self._failure(
                    started_at=started_at,
                    raw_response=raw_response,
                    status=ProviderResponseStatus.TIMED_OUT,
                    code="timeout",
                    message=str(error) or f"{self.name} request timed out",
                    retryable=True,
                    attempts=attempts,
                )
            except httpx.TransportError as error:
                if attempts <= self._max_retries:
                    await self._sleep(self._backoff_delay(attempts))
                    continue
                return self._failure(
                    started_at=started_at,
                    raw_response=raw_response,
                    status=ProviderResponseStatus.ERROR,
                    code="transport_error",
                    message=str(error) or f"{self.name} transport failed",
                    retryable=True,
                    attempts=attempts,
                )

            raw_response = self._read_json(response)
            if response.is_success:
                try:
                    normalized = self.normalize_response(raw_response)
                except (KeyError, TypeError, ValueError) as error:
                    return self._failure(
                        started_at=started_at,
                        raw_response=raw_response,
                        status=ProviderResponseStatus.ERROR,
                        code="invalid_response",
                        message=str(error) or f"{self.name} returned an invalid response",
                        retryable=False,
                        attempts=attempts,
                    )
                return ProviderResponse(
                    provider=self.name,
                    model_identifier=(normalized.model_identifier or self.model_identifier),
                    response_text=normalized.response_text,
                    citations=normalized.citations,
                    raw_response=raw_response,
                    token_usage=normalized.token_usage,
                    latency_ms=self._latency_ms(started_at),
                    status=ProviderResponseStatus.SUCCEEDED,
                )

            retryable = response.status_code in TRANSIENT_HTTP_STATUSES
            if retryable and attempts <= self._max_retries:
                await self._sleep(self._retry_delay(response, attempts))
                continue

            code, message = self._api_error(raw_response, response.status_code)
            status = (
                ProviderResponseStatus.RATE_LIMITED
                if response.status_code == 429
                else ProviderResponseStatus.ERROR
            )
            return self._failure(
                started_at=started_at,
                raw_response=raw_response,
                status=status,
                code=code,
                message=message,
                retryable=retryable,
                attempts=attempts,
                http_status=response.status_code,
            )

        raise RuntimeError("provider retry loop terminated unexpectedly")

    def _failure(
        self,
        *,
        started_at: float,
        raw_response: dict[str, Any],
        status: ProviderResponseStatus,
        code: str,
        message: str,
        retryable: bool,
        attempts: int,
        http_status: int | None = None,
    ) -> ProviderResponse:
        return ProviderResponse(
            provider=self.name,
            model_identifier=self.model_identifier,
            response_text="",
            citations=[],
            raw_response=raw_response,
            token_usage=TokenUsage(),
            latency_ms=self._latency_ms(started_at),
            status=status,
            error=ProviderError(
                code=code,
                message=message,
                retryable=retryable,
                attempts=attempts,
                http_status=http_status,
            ),
        )

    def _retry_delay(self, response: httpx.Response, attempts: int) -> float:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            parsed = self._parse_retry_after(retry_after)
            if parsed is not None:
                return min(parsed, self._max_retry_after_seconds)
        return self._backoff_delay(attempts)

    def _parse_retry_after(self, value: str) -> float | None:
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
            except (TypeError, ValueError):
                return None
            return max(0.0, retry_at.timestamp() - time())

    def _backoff_delay(self, attempts: int) -> float:
        return min(
            self._retry_backoff_seconds * (2 ** (attempts - 1)),
            self._max_retry_after_seconds,
        )

    @staticmethod
    def _read_json(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError:
            return {"unparsed_body": response.text}
        if isinstance(body, dict):
            return body
        return {"data": body}

    @staticmethod
    def _api_error(raw_response: dict[str, Any], http_status: int) -> tuple[str, str]:
        error = raw_response.get("error")
        if isinstance(error, dict):
            code = str(error.get("code") or error.get("type") or f"http_{http_status}")
            message = str(error.get("message") or error)
            return code, message
        detail = raw_response.get("detail")
        if detail:
            return f"http_{http_status}", str(detail)
        return f"http_{http_status}", f"Provider returned HTTP {http_status}"

    @staticmethod
    def _latency_ms(started_at: float) -> float:
        return max(0.0, (perf_counter() - started_at) * 1_000)
