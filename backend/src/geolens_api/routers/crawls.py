from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from geolens_api.crawler.errors import UrlValidationError
from geolens_api.crawler.urls import PublicUrlValidator
from geolens_api.database import get_session
from geolens_api.queues import CrawlQueue, get_crawl_queue
from geolens_api.schemas.job import CrawlJobResponse
from geolens_api.services.crawls import (
    CrawlJobNotFoundError,
    CrawlJobService,
    CrawlQueueUnavailableError,
    SiteNotFoundError,
)

router = APIRouter(tags=["crawls"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
QueueDependency = Annotated[CrawlQueue, Depends(get_crawl_queue)]


def get_url_validator() -> PublicUrlValidator:
    return PublicUrlValidator()


ValidatorDependency = Annotated[PublicUrlValidator, Depends(get_url_validator)]


@router.post(
    "/sites/{site_id}/crawls",
    response_model=CrawlJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_crawl(
    site_id: UUID,
    session: SessionDependency,
    queue: QueueDependency,
    validator: ValidatorDependency,
) -> CrawlJobResponse:
    try:
        job = await CrawlJobService(session).create(
            site_id,
            validator=validator,
            queue=queue,
        )
    except SiteNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except UrlValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except CrawlQueueUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    return CrawlJobResponse.model_validate(job)


@router.get(
    "/sites/{site_id}/crawls/latest",
    response_model=CrawlJobResponse | None,
)
async def get_latest_crawl_for_site(
    site_id: UUID,
    session: SessionDependency,
) -> CrawlJobResponse | None:
    job = await CrawlJobService(session).get_latest_for_site(site_id)
    return CrawlJobResponse.model_validate(job) if job is not None else None


@router.get("/crawls/{crawl_id}", response_model=CrawlJobResponse)
async def get_crawl(crawl_id: UUID, session: SessionDependency) -> CrawlJobResponse:
    try:
        job = await CrawlJobService(session).get(crawl_id)
    except CrawlJobNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return CrawlJobResponse.model_validate(job)
