import asyncio
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from geolens_api.crawler.crawler import WebsiteCrawler
from geolens_api.crawler.errors import CrawlerError
from geolens_api.crawler.types import CrawlFailure
from geolens_api.crawler.urls import PublicUrlValidator
from geolens_api.models.crawl_job import CrawlJob, CrawlJobStatus
from geolens_api.queues import CrawlQueue
from geolens_api.repositories.crawls import CrawlRepository


class SiteNotFoundError(Exception):
    def __init__(self, site_id: UUID) -> None:
        super().__init__(f"Site {site_id} was not found")
        self.site_id = site_id


class CrawlJobNotFoundError(Exception):
    def __init__(self, crawl_id: UUID) -> None:
        super().__init__(f"Crawl {crawl_id} was not found")
        self.crawl_id = crawl_id


class CrawlQueueUnavailableError(Exception):
    def __init__(self) -> None:
        super().__init__("The crawl could not be queued")


class CrawlJobService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._crawls = CrawlRepository(session)

    async def create(
        self,
        site_id: UUID,
        *,
        validator: PublicUrlValidator,
        queue: CrawlQueue,
    ) -> CrawlJob:
        site = await self._crawls.get_site(site_id)
        if site is None:
            raise SiteNotFoundError(site_id)
        site_url = site.url
        await self._session.commit()
        await validator.validate(site_url)

        job = await self._crawls.create_job(site_id)
        await self._session.commit()
        try:
            job.celery_task_id = await asyncio.to_thread(queue.enqueue, job.id)
        except Exception:
            job.status = CrawlJobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = "The crawl could not be queued"
            self._crawls.add_error(
                job.id,
                CrawlFailure(
                    url=site_url,
                    depth=None,
                    stage="queue",
                    error_type="queue_unavailable",
                    message=job.error_message,
                ),
            )
            job.error_count = 1
            await self._session.commit()
            raise CrawlQueueUnavailableError from None
        await self._session.commit()
        await self._session.refresh(job)
        return job

    async def get(self, crawl_id: UUID) -> CrawlJob:
        job = await self._crawls.get_job(crawl_id)
        if job is None:
            raise CrawlJobNotFoundError(crawl_id)
        return job

    async def get_latest_for_site(self, site_id: UUID) -> CrawlJob | None:
        return await self._crawls.get_latest_job_for_site(site_id)


class CrawlExecutionService:
    def __init__(self, session: AsyncSession, crawler: WebsiteCrawler) -> None:
        self._session = session
        self._crawler = crawler
        self._crawls = CrawlRepository(session)

    async def run(self, crawl_id: UUID) -> None:
        job = await self._crawls.get_job_for_execution(crawl_id)
        if job is None:
            raise CrawlJobNotFoundError(crawl_id)
        if job.status not in {CrawlJobStatus.PENDING, CrawlJobStatus.RUNNING}:
            return

        job.status = CrawlJobStatus.RUNNING
        job.started_at = job.started_at or datetime.now(timezone.utc)
        job.completed_at = None
        job.error_message = None
        await self._session.commit()

        try:
            report = await self._crawler.crawl(job.site.url)
        except Exception as error:
            failure = CrawlFailure(
                url=job.site.url,
                depth=0,
                stage=error.stage if isinstance(error, CrawlerError) else "crawl",
                error_type=(
                    error.error_type if isinstance(error, CrawlerError) else "execution_failed"
                ),
                message=str(error) or error.__class__.__name__,
            )
            self._crawls.add_error(job.id, failure)
            job.status = CrawlJobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = failure.message
            job.error_count = 1
            await self._session.commit()
            raise

        self._crawls.add_report(job.id, report)
        job.page_count = len(report.pages)
        job.error_count = len(report.errors)
        job.status = CrawlJobStatus.SUCCEEDED
        job.completed_at = datetime.now(timezone.utc)
        await self._session.commit()
