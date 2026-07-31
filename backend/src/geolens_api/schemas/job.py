from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from geolens_api.models.analysis_run import AnalysisRunStatus
from geolens_api.models.crawl_job import CrawlJobStatus


class CrawlJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    site_id: UUID
    status: CrawlJobStatus
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    celery_task_id: str | None
    page_count: int
    error_count: int
    created_at: datetime
    updated_at: datetime


class AnalysisRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    crawl_job_id: UUID | None
    status: AnalysisRunStatus
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    celery_task_id: str | None
    provider_configurations: list[dict[str, str]]
    prompts: list[str]
    claim_classifier_configuration: dict[str, str] | None
    created_at: datetime
    updated_at: datetime
