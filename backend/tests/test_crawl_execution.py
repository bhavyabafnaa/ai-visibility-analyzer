from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from geolens_api.crawler.crawler import CrawlLimits, WebsiteCrawler
from geolens_api.crawler.urls import PublicUrlValidator
from geolens_api.models import CrawlError, CrawlJob, CrawlJobStatus, CrawlPage, Project, Site
from geolens_api.services.crawls import CrawlExecutionService
from tests.fixture_site import FixtureSite, StaticResolver


async def test_execution_persists_pages_errors_hashes_and_job_counts(
    session: AsyncSession,
) -> None:
    project = Project(name="Persisted crawl", site=Site(url="https://fixture.test/"))
    session.add(project)
    await session.flush()
    assert project.site is not None
    job = CrawlJob(site_id=project.site.id)
    session.add(job)
    await session.commit()

    fixture_site = FixtureSite()
    crawler = WebsiteCrawler(
        limits=CrawlLimits(
            page_limit=20,
            max_depth=2,
            max_response_bytes=1_300,
            timeout_seconds=1,
            concurrency=3,
        ),
        user_agent="GeoLensBot/Test",
        validator=PublicUrlValidator(StaticResolver()),
        transport=fixture_site.transport,
    )

    await CrawlExecutionService(session, crawler).run(job.id)

    pages = list(
        (
            await session.scalars(
                select(CrawlPage).where(CrawlPage.crawl_job_id == job.id).order_by(CrawlPage.url)
            )
        ).all()
    )
    errors = list(
        (
            await session.scalars(
                select(CrawlError)
                .where(CrawlError.crawl_job_id == job.id)
                .order_by(CrawlError.error_type)
            )
        ).all()
    )
    await session.refresh(job)

    assert job.status == CrawlJobStatus.SUCCEEDED
    assert job.started_at is not None
    assert job.completed_at is not None
    assert job.page_count == len(pages) == 5
    assert job.error_count == len(errors)
    assert all(len(page.content_hash) == 64 for page in pages)
    assert any(error.error_type == "robots_disallowed" for error in errors)
    assert any(error.error_type == "redirect_loop" for error in errors)
    assert any(error.error_type == "response_too_large" for error in errors)
