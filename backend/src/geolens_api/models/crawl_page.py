from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from geolens_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from geolens_api.models.crawl_job import CrawlJob


class CrawlPage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crawl_pages"
    __table_args__ = (
        UniqueConstraint("crawl_job_id", "url", name="uq_crawl_pages_crawl_job_id_url"),
    )

    crawl_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(String(2048))
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    headings: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    main_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_data: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    internal_links: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    response_size: Mapped[int] = mapped_column(Integer, nullable=False)

    crawl_job: Mapped["CrawlJob"] = relationship(back_populates="pages")
