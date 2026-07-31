import asyncio
import hashlib

import httpx

from geolens_api.crawler.crawler import CrawlLimits, WebsiteCrawler
from geolens_api.crawler.renderer import RenderedPage, RenderRequest
from geolens_api.crawler.urls import PublicUrlValidator
from tests.fixture_site import FIXTURE_ROOT, FixtureSite, StaticResolver


def fixture_crawler(
    site: FixtureSite,
    *,
    page_limit: int = 20,
    max_depth: int = 2,
    concurrency: int = 3,
) -> WebsiteCrawler:
    return WebsiteCrawler(
        limits=CrawlLimits(
            page_limit=page_limit,
            max_depth=max_depth,
            max_response_bytes=1_300,
            timeout_seconds=1,
            concurrency=concurrency,
            max_redirects=4,
            sitemap_limit=4,
        ),
        user_agent="GeoLensBot/Test",
        validator=PublicUrlValidator(StaticResolver()),
        transport=site.transport,
    )


async def test_crawler_is_deterministic_bounded_and_domain_scoped() -> None:
    first_site = FixtureSite()
    second_site = FixtureSite()

    first = await fixture_crawler(first_site).crawl("https://fixture.test")
    second = await fixture_crawler(second_site).crawl("https://fixture.test")

    assert first == second
    assert first.attempted_pages <= 20
    assert {page.url for page in first.pages} == {
        "https://fixture.test/",
        "https://fixture.test/about.html",
        "https://fixture.test/canonical-a.html",
        "https://fixture.test/deep.html",
        "https://fixture.test/malformed.html",
    }
    canonical_pages = [
        page for page in first.pages if page.canonical_url == "https://fixture.test/canonical.html"
    ]
    assert len(canonical_pages) == 1
    assert "/private.html" not in first_site.requested_paths
    assert all(host == "fixture.test" for host in first_site.requested_hosts)
    assert not any("outside.example" in host for host in first_site.requested_hosts)
    assert {error.error_type for error in first.errors} >= {
        "http_status",
        "redirect_loop",
        "response_too_large",
        "robots_disallowed",
    }

    home = next(page for page in first.pages if page.url == "https://fixture.test/")
    fixture_body = (FIXTURE_ROOT / "index.html").read_bytes()
    assert home.content_hash == hashlib.sha256(fixture_body).hexdigest()
    assert len(home.content_hash) == 64
    assert home.title == "Fixture home"
    assert home.description == "A deterministic local crawler fixture."
    assert home.headings[0] == {"level": 1, "text": "Fixture heading"}
    assert home.structured_data[0] == {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Fixture Site",
    }


async def test_sitemap_urls_take_priority_over_seed_url() -> None:
    site = FixtureSite()

    report = await fixture_crawler(site, page_limit=1, concurrency=1).crawl("https://fixture.test/")

    assert report.attempted_pages == 1
    assert [page.url for page in report.pages] == ["https://fixture.test/canonical-a.html"]


async def test_depth_limit_prevents_child_fetches() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        if request.url.path in {"/robots.txt", "/sitemap.xml"}:
            return httpx.Response(404)
        if request.url.path == "/":
            return httpx.Response(
                200,
                headers={"Content-Type": "text/html"},
                text='<main><a href="/child">Child</a></main>',
            )
        return httpx.Response(200, text="<main>Child</main>")

    crawler = WebsiteCrawler(
        limits=CrawlLimits(page_limit=5, max_depth=0, concurrency=2),
        user_agent="GeoLensBot/Test",
        validator=PublicUrlValidator(StaticResolver()),
        transport=httpx.MockTransport(handler),
    )

    report = await crawler.crawl("https://fixture.test/")

    assert [page.url for page in report.pages] == ["https://fixture.test/"]
    assert "/child" not in requested


async def test_off_domain_redirect_is_rejected_before_dns_or_http() -> None:
    resolver = StaticResolver()
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        if request.url.path in {"/robots.txt", "/sitemap.xml"}:
            return httpx.Response(404)
        return httpx.Response(
            302,
            headers={"Location": "https://outside.example/private"},
        )

    crawler = WebsiteCrawler(
        limits=CrawlLimits(page_limit=1, max_depth=0, concurrency=1),
        user_agent="GeoLensBot/Test",
        validator=PublicUrlValidator(resolver),
        transport=httpx.MockTransport(handler),
    )

    report = await crawler.crawl("https://fixture.test/")

    assert report.pages == []
    assert any(error.error_type == "off_domain" for error in report.errors)
    assert resolver.calls == [("fixture.test", 443)]
    assert requested == ["/robots.txt", "/sitemap.xml", "/"]


async def test_total_request_timeout_is_enforced() -> None:
    async def slow_handler(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.05)
        return httpx.Response(200, text="<main>Too late</main>")

    crawler = WebsiteCrawler(
        limits=CrawlLimits(
            page_limit=1,
            max_depth=0,
            timeout_seconds=0.005,
            concurrency=1,
        ),
        user_agent="GeoLensBot/Test",
        validator=PublicUrlValidator(StaticResolver()),
        transport=httpx.MockTransport(slow_handler),
    )

    report = await crawler.crawl("https://fixture.test/")

    assert report.pages == []
    assert any(error.error_type == "timeout" for error in report.errors)


async def test_concurrency_limit_caps_simultaneous_page_requests() -> None:
    active = 0
    maximum_active = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, maximum_active
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path == "/sitemap.xml":
            locations = "".join(
                f"<url><loc>https://fixture.test/page-{index}</loc></url>" for index in range(4)
            )
            return httpx.Response(200, content=f"<urlset>{locations}</urlset>")
        active += 1
        maximum_active = max(maximum_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html"},
            text=f"<main>{request.url.path}</main>",
        )

    crawler = WebsiteCrawler(
        limits=CrawlLimits(page_limit=4, max_depth=0, concurrency=2),
        user_agent="GeoLensBot/Test",
        validator=PublicUrlValidator(StaticResolver()),
        transport=httpx.MockTransport(handler),
    )

    report = await crawler.crawl("https://fixture.test/")

    assert report.attempted_pages == 4
    assert len(report.pages) == 4
    assert maximum_active == 2


async def test_optional_renderer_fallback_is_bounded_and_reextracted() -> None:
    class FixtureRenderer:
        requests: list[RenderRequest]

        def __init__(self) -> None:
            self.requests = []

        async def render(self, request: RenderRequest) -> RenderedPage:
            self.requests.append(request)
            return RenderedPage(
                html="<html><head><title>Rendered</title></head>"
                "<body><main><h1>JavaScript content</h1></main></body></html>",
                final_url=request.url,
            )

    renderer = FixtureRenderer()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path in {"/robots.txt", "/sitemap.xml"}:
            return httpx.Response(404)
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html"},
            text="<html><body><main></main></body></html>",
        )

    crawler = WebsiteCrawler(
        limits=CrawlLimits(page_limit=1, max_depth=0, concurrency=1),
        user_agent="GeoLensBot/Test",
        validator=PublicUrlValidator(StaticResolver()),
        renderer=renderer,
        transport=httpx.MockTransport(handler),
    )

    report = await crawler.crawl("https://fixture.test/")

    assert len(renderer.requests) == 1
    assert report.pages[0].title == "Rendered"
    assert report.pages[0].main_text == "JavaScript content"
