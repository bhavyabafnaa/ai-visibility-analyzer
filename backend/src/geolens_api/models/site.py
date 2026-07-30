from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from geolens_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from geolens_api.models.crawl_job import CrawlJob
    from geolens_api.models.project import Project


class Site(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sites"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)

    project: Mapped["Project"] = relationship(back_populates="site")
    crawl_jobs: Mapped[list["CrawlJob"]] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
    )
