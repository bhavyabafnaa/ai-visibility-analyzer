from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from geolens_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from geolens_api.models.crawl_job import CrawlJob
    from geolens_api.models.project import Project


class AnalysisRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AnalysisRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analysis_runs"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    crawl_job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="SET NULL"),
        index=True,
    )
    status: Mapped[AnalysisRunStatus] = mapped_column(
        SqlEnum(
            AnalysisRunStatus,
            name="analysis_run_status",
            native_enum=False,
            length=32,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=AnalysisRunStatus.PENDING,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    project: Mapped["Project"] = relationship(back_populates="analysis_runs")
    crawl_job: Mapped["CrawlJob | None"] = relationship(back_populates="analysis_runs")
