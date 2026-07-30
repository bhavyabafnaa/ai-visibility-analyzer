import asyncio
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from geolens_api.crawler.errors import (
    FetchError,
    FetchTimeoutError,
    InvalidRedirectError,
    OffDomainError,
    RedirectLoopError,
    ResponseTooLargeError,
    TooManyRedirectsError,
    UrlValidationError,
)
from geolens_api.crawler.urls import PublicUrlValidator, normalize_url

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


@dataclass(frozen=True)
class FetchResponse:
    url: str
    status_code: int
    headers: httpx.Headers
    body: bytes


class HttpxPageFetcher:
    """Bounded HTTPX fetcher that connects only to validated, pinned IP addresses."""

    def __init__(
        self,
        *,
        validator: PublicUrlValidator,
        user_agent: str,
        timeout_seconds: float,
        max_response_bytes: int,
        max_redirects: int,
        concurrency: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._validator = validator
        self._user_agent = user_agent
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._max_redirects = max_redirects
        self._client = httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(timeout_seconds),
            limits=httpx.Limits(
                max_connections=concurrency,
                max_keepalive_connections=concurrency,
            ),
            transport=transport,
            trust_env=False,
        )

    async def __aenter__(self) -> "HttpxPageFetcher":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    async def fetch(self, url: str, *, allowed_hostname: str) -> FetchResponse:
        current_url = normalize_url(url).url
        visited: set[str] = set()
        redirect_count = 0

        while True:
            if current_url in visited:
                raise RedirectLoopError(f"Redirect loop detected at {current_url}")
            visited.add(current_url)

            normalized = normalize_url(current_url)
            if normalized.hostname != allowed_hostname:
                raise OffDomainError(f"Refusing to leave configured domain {allowed_hostname!r}")
            validated = await self._validator.validate(normalized.url)

            try:
                response = await asyncio.wait_for(
                    self._request_once(
                        validated.transport_url,
                        validated.host_header,
                        validated.normalized.hostname,
                    ),
                    timeout=self._timeout_seconds,
                )
            except asyncio.TimeoutError as error:
                raise FetchTimeoutError(f"Timed out fetching {current_url}") from error
            except httpx.TimeoutException as error:
                raise FetchTimeoutError(f"Timed out fetching {current_url}") from error
            except httpx.RequestError as error:
                raise FetchError(f"HTTP request failed for {current_url}: {error}") from error

            if response.status_code not in _REDIRECT_STATUSES:
                return FetchResponse(
                    url=current_url,
                    status_code=response.status_code,
                    headers=response.headers,
                    body=response.body,
                )

            location = response.headers.get("location")
            if not location:
                raise InvalidRedirectError(
                    f"Redirect response from {current_url} did not include Location"
                )
            if redirect_count >= self._max_redirects:
                raise TooManyRedirectsError(
                    f"Exceeded {self._max_redirects} redirects while fetching {url}"
                )
            try:
                current_url = normalize_url(urljoin(current_url, location)).url
            except UrlValidationError as error:
                raise InvalidRedirectError(
                    f"Redirect response from {current_url} had an invalid Location"
                ) from error
            redirect_count += 1

    async def _request_once(
        self,
        transport_url: str,
        host_header: str,
        sni_hostname: str,
    ) -> FetchResponse:
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml,text/xml;q=0.9,*/*;q=0.1",
            "Host": host_header,
            "User-Agent": self._user_agent,
        }
        async with self._client.stream(
            "GET",
            transport_url,
            headers=headers,
            extensions={"sni_hostname": sni_hostname},
        ) as response:
            content_length = response.headers.get("content-length")
            if content_length is not None:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    declared_size = 0
                if declared_size > self._max_response_bytes:
                    raise ResponseTooLargeError(
                        f"Response declares {declared_size} bytes; "
                        f"limit is {self._max_response_bytes}"
                    )

            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > self._max_response_bytes:
                    raise ResponseTooLargeError(
                        f"Response exceeded {self._max_response_bytes} bytes"
                    )
            return FetchResponse(
                url=transport_url,
                status_code=response.status_code,
                headers=response.headers,
                body=bytes(body),
            )
