from typing import TYPE_CHECKING

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from geolens_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from geolens_api.models.analysis_run import AnalysisRun
    from geolens_api.models.competitor import Competitor
    from geolens_api.models.site import Site


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    site: Mapped["Site | None"] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )
    competitors: Mapped[list["Competitor"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
