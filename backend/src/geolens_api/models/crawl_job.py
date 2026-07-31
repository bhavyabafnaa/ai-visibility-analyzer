from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from geolens_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from geolens_api.models.analysis_run import AnalysisRun
    from geolens_api.models.crawl_error import CrawlError
    from geolens_api.models.crawl_page import CrawlPage
    from geolens_api.models.site import Site


class CrawlJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CrawlJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crawl_jobs"

    site_id: Mapped[UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[CrawlJobStatus] = mapped_column(
        SqlEnum(
            CrawlJobStatus,
            name="crawl_job_status",
            native_enum=False,
            length=32,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=CrawlJobStatus.PENDING,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    celery_task_id: Mapped[str | None] = mapped_column(String(255))
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    site: Mapped["Site"] = relationship(back_populates="crawl_jobs")
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(back_populates="crawl_job")
    pages: Mapped[list["CrawlPage"]] = relationship(
        back_populates="crawl_job",
        cascade="all, delete-orphan",
    )
    errors: Mapped[list["CrawlError"]] = relationship(
        back_populates="crawl_job",
        cascade="all, delete-orphan",
    )
