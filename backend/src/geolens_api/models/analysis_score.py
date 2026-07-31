from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from geolens_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from geolens_api.models.analysis_run import AnalysisRun


class AnalysisScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analysis_scores"
    __table_args__ = (
        UniqueConstraint(
            "analysis_run_id",
            "name",
            name="uq_analysis_scores_analysis_run_id_name",
        ),
    )

    analysis_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    numerator: Mapped[float] = mapped_column(Float, nullable=False)
    denominator: Mapped[float] = mapped_column(Float, nullable=False)
    value: Mapped[float | None] = mapped_column(Float)
    percentage: Mapped[float | None] = mapped_column(Float)
    is_defined: Mapped[bool] = mapped_column(Boolean, nullable=False)
    method: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(64), nullable=False)
    is_objective_truth: Mapped[bool | None] = mapped_column(Boolean)
    disclaimer: Mapped[str | None] = mapped_column(Text)

    analysis_run: Mapped["AnalysisRun"] = relationship(back_populates="scores")
