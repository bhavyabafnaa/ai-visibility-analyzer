from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from geolens_api.crawler.types import CrawledPage, CrawlFailure, CrawlReport
from geolens_api.models.crawl_error import CrawlError
from geolens_api.models.crawl_job import CrawlJob
from geolens_api.models.crawl_page import CrawlPage
from geolens_api.models.site import Site


class CrawlRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_site(self, site_id: UUID) -> Site | None:
        return await self._session.get(Site, site_id)

    async def create_job(self, site_id: UUID) -> CrawlJob:
        job = CrawlJob(site_id=site_id)
        self._session.add(job)
        await self._session.flush()
        return job

    async def get_job(self, crawl_id: UUID) -> CrawlJob | None:
        return await self._session.get(CrawlJob, crawl_id)

    async def get_latest_job_for_site(self, site_id: UUID) -> CrawlJob | None:
        statement = (
            select(CrawlJob)
            .where(CrawlJob.site_id == site_id)
            .order_by(CrawlJob.created_at.desc(), CrawlJob.id.desc())
            .limit(1)
        )
        job: CrawlJob | None = await self._session.scalar(statement)
        return job

    async def get_job_for_execution(self, crawl_id: UUID) -> CrawlJob | None:
        statement = (
            select(CrawlJob).where(CrawlJob.id == crawl_id).options(selectinload(CrawlJob.site))
        )
        job: CrawlJob | None = await self._session.scalar(statement)
        return job

    def add_report(self, crawl_id: UUID, report: CrawlReport) -> None:
        for page in report.pages:
            self._session.add(self._page_model(crawl_id, page))
        for error in report.errors:
            self._session.add(self._error_model(crawl_id, error))

    def add_error(self, crawl_id: UUID, error: CrawlFailure) -> None:
        self._session.add(self._error_model(crawl_id, error))

    @staticmethod
    def _page_model(crawl_id: UUID, page: CrawledPage) -> CrawlPage:
        return CrawlPage(
            crawl_job_id=crawl_id,
            url=page.url,
            canonical_url=page.canonical_url,
            title=page.title,
            description=page.description,
            headings=list(page.headings),
            main_text=page.main_text,
            structured_data=list(page.structured_data),
            internal_links=list(page.internal_links),
            content_hash=page.content_hash,
            status_code=page.status_code,
            depth=page.depth,
            content_type=page.content_type,
            response_size=page.response_size,
        )

    @staticmethod
    def _error_model(crawl_id: UUID, error: CrawlFailure) -> CrawlError:
        return CrawlError(
            crawl_job_id=crawl_id,
            url=error.url,
            depth=error.depth,
            stage=error.stage,
            error_type=error.error_type,
            message=error.message,
        )
