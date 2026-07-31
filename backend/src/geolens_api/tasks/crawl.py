import asyncio
from uuid import UUID

from geolens_api.celery_app import celery_app
from geolens_api.config import get_settings
from geolens_api.crawler.crawler import CrawlLimits, WebsiteCrawler
from geolens_api.database import async_session_factory, engine
from geolens_api.services.crawls import CrawlExecutionService


@celery_app.task(name="geolens.crawl_site")
def crawl_site(crawl_id: str) -> None:
    asyncio.run(_run_crawl(UUID(crawl_id)))


async def _run_crawl(crawl_id: UUID) -> None:
    settings = get_settings()
    crawler = WebsiteCrawler(
        limits=CrawlLimits(
            page_limit=settings.crawler_page_limit,
            max_depth=settings.crawler_max_depth,
            max_response_bytes=settings.crawler_max_response_bytes,
            timeout_seconds=settings.crawler_timeout_seconds,
            concurrency=settings.crawler_concurrency,
            max_redirects=settings.crawler_max_redirects,
            sitemap_limit=settings.crawler_sitemap_limit,
            renderer_min_text_characters=settings.crawler_renderer_min_text_characters,
        ),
        user_agent=settings.crawler_user_agent,
    )
    try:
        async with async_session_factory() as session:
            await CrawlExecutionService(session, crawler).run(crawl_id)
    finally:
        await engine.dispose()
