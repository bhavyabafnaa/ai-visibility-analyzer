import asyncio
import hashlib
import heapq
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from geolens_api.crawler.errors import CrawlerError, OffDomainError, UrlValidationError
from geolens_api.crawler.extractor import extract_html
from geolens_api.crawler.fetcher import FetchResponse, HttpxPageFetcher
from geolens_api.crawler.renderer import PageRenderer, RenderRequest
from geolens_api.crawler.robots import RobotsPolicy
from geolens_api.crawler.types import CrawledPage, CrawlFailure, CrawlReport, ExtractedPage
from geolens_api.crawler.urls import PublicUrlValidator, normalize_url


@dataclass(frozen=True)
class CrawlLimits:
    page_limit: int = 100
    max_depth: int = 3
    max_response_bytes: int = 2_000_000
    timeout_seconds: float = 10.0
    concurrency: int = 5
    max_redirects: int = 5
    sitemap_limit: int = 20
    renderer_min_text_characters: int = 80

    def __post_init__(self) -> None:
        if self.page_limit < 1:
            raise ValueError("page_limit must be positive")
        if self.max_depth < 0:
            raise ValueError("max_depth cannot be negative")
        if self.max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.concurrency < 1:
            raise ValueError("concurrency must be positive")
        if self.max_redirects < 0:
            raise ValueError("max_redirects cannot be negative")
        if self.sitemap_limit < 1:
            raise ValueError("sitemap_limit must be positive")


class WebsiteCrawler:
    """Deterministic, domain-scoped website crawler."""

    def __init__(
        self,
        *,
        limits: CrawlLimits,
        user_agent: str,
        validator: PublicUrlValidator | None = None,
        renderer: PageRenderer | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._limits = limits
        self._user_agent = user_agent
        self._validator = validator or PublicUrlValidator()
        self._renderer = renderer
        self._transport = transport

    async def crawl(self, root_url: str) -> CrawlReport:
        root = (await self._validator.validate(root_url)).normalized
        report = CrawlReport()

        async with HttpxPageFetcher(
            validator=self._validator,
            user_agent=self._user_agent,
            timeout_seconds=self._limits.timeout_seconds,
            max_response_bytes=self._limits.max_response_bytes,
            max_redirects=self._limits.max_redirects,
            concurrency=self._limits.concurrency,
            transport=self._transport,
        ) as fetcher:
            robots = await self._load_robots(fetcher, root.url, root.hostname, report)
            sitemap_urls = await self._discover_sitemaps(
                fetcher,
                root.url,
                root.hostname,
                robots,
                report,
            )
            await self._crawl_pages(
                fetcher,
                root.url,
                root.hostname,
                robots,
                sitemap_urls,
                report,
            )
        return report

    async def _load_robots(
        self,
        fetcher: HttpxPageFetcher,
        root_url: str,
        hostname: str,
        report: CrawlReport,
    ) -> RobotsPolicy:
        robots_url = normalize_url(urljoin(root_url, "/robots.txt")).url
        try:
            response = await fetcher.fetch(robots_url, allowed_hostname=hostname)
        except CrawlerError as error:
            report.errors.append(self._failure(error, robots_url, None, stage="robots"))
            return RobotsPolicy.allow_all(robots_url)

        if response.status_code == 200:
            return RobotsPolicy.parse(
                response.body.decode("utf-8", errors="replace"),
                robots_url,
            )
        if response.status_code in {401, 403} or response.status_code >= 500:
            report.errors.append(
                CrawlFailure(
                    url=robots_url,
                    depth=None,
                    stage="robots",
                    error_type="robots_unavailable",
                    message=f"robots.txt returned HTTP {response.status_code}; crawl denied",
                )
            )
            return RobotsPolicy.disallow_all(robots_url)
        if response.status_code != 404:
            report.errors.append(
                CrawlFailure(
                    url=robots_url,
                    depth=None,
                    stage="robots",
                    error_type="http_status",
                    message=f"robots.txt returned HTTP {response.status_code}",
                )
            )
        return RobotsPolicy.allow_all(robots_url)

    async def _discover_sitemaps(
        self,
        fetcher: HttpxPageFetcher,
        root_url: str,
        hostname: str,
        robots: RobotsPolicy,
        report: CrawlReport,
    ) -> list[str]:
        default_sitemap = normalize_url(urljoin(root_url, "/sitemap.xml")).url
        pending = list(robots.sitemap_urls)
        if default_sitemap not in pending:
            pending.append(default_sitemap)

        seen_sitemaps: set[str] = set()
        discovered_pages: set[str] = set()
        processed_sitemaps = 0
        while pending and processed_sitemaps < self._limits.sitemap_limit:
            sitemap_url = pending.pop(0)
            if sitemap_url in seen_sitemaps:
                continue
            seen_sitemaps.add(sitemap_url)
            try:
                normalized_sitemap = normalize_url(sitemap_url)
            except UrlValidationError:
                continue
            if normalized_sitemap.hostname != hostname:
                continue

            processed_sitemaps += 1
            try:
                response = await fetcher.fetch(
                    normalized_sitemap.url,
                    allowed_hostname=hostname,
                )
            except CrawlerError as error:
                report.errors.append(
                    self._failure(error, normalized_sitemap.url, None, stage="sitemap")
                )
                continue
            if response.status_code == 404 and normalized_sitemap.url == default_sitemap:
                continue
            if response.status_code != 200:
                report.errors.append(
                    CrawlFailure(
                        url=normalized_sitemap.url,
                        depth=None,
                        stage="sitemap",
                        error_type="http_status",
                        message=f"Sitemap returned HTTP {response.status_code}",
                    )
                )
                continue

            try:
                document = ElementTree.fromstring(response.body)
            except (ElementTree.ParseError, DefusedXmlException, ValueError) as error:
                report.errors.append(
                    CrawlFailure(
                        url=normalized_sitemap.url,
                        depth=None,
                        stage="sitemap",
                        error_type="invalid_sitemap",
                        message=f"Could not parse sitemap: {error}",
                    )
                )
                continue

            document_type = self._local_name(document.tag)
            locations = [
                (element.text or "").strip()
                for element in document.iter()
                if self._local_name(element.tag) == "loc" and (element.text or "").strip()
            ]
            for location in locations:
                try:
                    normalized_location = normalize_url(urljoin(normalized_sitemap.url, location))
                except UrlValidationError:
                    continue
                if normalized_location.hostname != hostname:
                    continue
                if document_type == "sitemapindex":
                    if normalized_location.url not in seen_sitemaps:
                        pending.append(normalized_location.url)
                elif document_type == "urlset":
                    discovered_pages.add(normalized_location.url)

        return sorted(discovered_pages)

    async def _crawl_pages(
        self,
        fetcher: HttpxPageFetcher,
        root_url: str,
        hostname: str,
        robots: RobotsPolicy,
        sitemap_urls: list[str],
        report: CrawlReport,
    ) -> None:
        queue: list[tuple[int, int, str]] = []
        scheduled: set[str] = set()
        known_identities: set[str] = set()

        def schedule(priority: int, depth: int, url: str) -> None:
            if depth > self._limits.max_depth or url in scheduled:
                return
            scheduled.add(url)
            heapq.heappush(queue, (priority, depth, url))

        for sitemap_url in sitemap_urls:
            schedule(0, 0, sitemap_url)
        schedule(1, 0, root_url)

        while queue and report.attempted_pages < self._limits.page_limit:
            batch: list[tuple[int, str]] = []
            remaining = self._limits.page_limit - report.attempted_pages
            while queue and len(batch) < min(self._limits.concurrency, remaining):
                _, depth, url = heapq.heappop(queue)
                if url in known_identities:
                    continue
                if not robots.allows(self._user_agent, url):
                    report.errors.append(
                        CrawlFailure(
                            url=url,
                            depth=depth,
                            stage="robots",
                            error_type="robots_disallowed",
                            message="URL is excluded by robots.txt",
                        )
                    )
                    continue
                batch.append((depth, url))

            if not batch:
                continue
            report.attempted_pages += len(batch)
            responses = await asyncio.gather(
                *[fetcher.fetch(url, allowed_hostname=hostname) for _, url in batch],
                return_exceptions=True,
            )

            for (depth, requested_url), result in zip(batch, responses, strict=True):
                if isinstance(result, asyncio.CancelledError):
                    raise result
                if isinstance(result, BaseException):
                    if isinstance(result, CrawlerError):
                        report.errors.append(self._failure(result, requested_url, depth))
                    else:
                        report.errors.append(
                            CrawlFailure(
                                url=requested_url,
                                depth=depth,
                                stage="fetch",
                                error_type="unexpected_fetch_error",
                                message=str(result),
                            )
                        )
                    continue

                try:
                    page_result = await self._process_response(
                        result,
                        depth,
                        hostname,
                        report,
                    )
                except Exception as error:
                    report.errors.append(
                        CrawlFailure(
                            url=result.url,
                            depth=depth,
                            stage="extract",
                            error_type="extraction_failed",
                            message=str(error) or error.__class__.__name__,
                        )
                    )
                    continue
                if page_result is None:
                    continue
                page, extracted = page_result

                identity = page.url
                if extracted.canonical_url is not None:
                    canonical = normalize_url(extracted.canonical_url)
                    if canonical.hostname == hostname:
                        identity = canonical.url
                duplicate = identity in known_identities or page.url in known_identities
                known_identities.add(page.url)
                known_identities.add(identity)
                if not duplicate:
                    report.pages.append(page)

                if depth < self._limits.max_depth:
                    for link in extracted.internal_links:
                        schedule(2, depth + 1, link)

    async def _process_response(
        self,
        response: FetchResponse,
        depth: int,
        hostname: str,
        report: CrawlReport,
    ) -> tuple[CrawledPage, ExtractedPage] | None:
        if not 200 <= response.status_code < 300:
            report.errors.append(
                CrawlFailure(
                    url=response.url,
                    depth=depth,
                    stage="fetch",
                    error_type="http_status",
                    message=f"Page returned HTTP {response.status_code}",
                )
            )
            return None

        content_type = response.headers.get("content-type")
        media_type = content_type.split(";", maxsplit=1)[0].strip().lower() if content_type else ""
        if media_type and media_type not in {"text/html", "application/xhtml+xml"}:
            report.errors.append(
                CrawlFailure(
                    url=response.url,
                    depth=depth,
                    stage="extract",
                    error_type="unsupported_content_type",
                    message=f"Unsupported content type {media_type!r}",
                )
            )
            return None

        body = response.body
        extracted = extract_html(body, response.url, hostname)
        final_url = response.url
        if (
            self._renderer is not None
            and len(extracted.main_text) < self._limits.renderer_min_text_characters
        ):
            try:
                rendered = await asyncio.wait_for(
                    self._renderer.render(
                        RenderRequest(
                            url=response.url,
                            allowed_hostname=hostname,
                            timeout_seconds=self._limits.timeout_seconds,
                            max_response_bytes=self._limits.max_response_bytes,
                        )
                    ),
                    timeout=self._limits.timeout_seconds,
                )
                normalized_rendered_url = normalize_url(rendered.final_url)
                if normalized_rendered_url.hostname != hostname:
                    raise OffDomainError("Renderer left the configured domain")
                rendered_url = await self._validator.validate(normalized_rendered_url.url)
                rendered_body = rendered.html.encode("utf-8")
                if len(rendered_body) > self._limits.max_response_bytes:
                    raise ValueError("Rendered page exceeded the response-size limit")
                body = rendered_body
                final_url = rendered_url.normalized.url
                extracted = extract_html(body, final_url, hostname)
            except Exception as error:
                report.errors.append(
                    CrawlFailure(
                        url=response.url,
                        depth=depth,
                        stage="renderer",
                        error_type="renderer_failed",
                        message=str(error),
                    )
                )

        return (
            CrawledPage(
                url=final_url,
                canonical_url=extracted.canonical_url,
                title=extracted.title,
                description=extracted.description,
                headings=extracted.headings,
                main_text=extracted.main_text,
                structured_data=extracted.structured_data,
                internal_links=extracted.internal_links,
                content_hash=hashlib.sha256(body).hexdigest(),
                status_code=response.status_code,
                depth=depth,
                content_type=content_type,
                response_size=len(body),
            ),
            extracted,
        )

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", maxsplit=1)[-1].lower()

    @staticmethod
    def _failure(
        error: CrawlerError,
        url: str | None,
        depth: int | None,
        *,
        stage: str | None = None,
    ) -> CrawlFailure:
        return CrawlFailure(
            url=url,
            depth=depth,
            stage=stage or error.stage,
            error_type=error.error_type,
            message=str(error),
        )
