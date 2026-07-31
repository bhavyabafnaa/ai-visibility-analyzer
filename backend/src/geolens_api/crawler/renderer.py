from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RenderRequest:
    url: str
    allowed_hostname: str
    timeout_seconds: float
    max_response_bytes: int


@dataclass(frozen=True)
class RenderedPage:
    html: str
    final_url: str


class PageRenderer(Protocol):
    """Optional JavaScript renderer.

    Implementations such as Playwright must intercept every navigation and subresource
    request, enforce ``allowed_hostname``, reject non-public resolved addresses, and honor
    both limits in the request. The crawler revalidates the returned final URL and size.
    """

    async def render(self, request: RenderRequest) -> RenderedPage: ...
