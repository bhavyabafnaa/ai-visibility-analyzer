from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from geolens_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from geolens_api.models.crawl_job import CrawlJob


class CrawlError(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crawl_errors"

    crawl_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str | None] = mapped_column(String(2048))
    depth: Mapped[int | None] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    crawl_job: Mapped["CrawlJob"] = relationship(back_populates="errors")
