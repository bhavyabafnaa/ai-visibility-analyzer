from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from geolens_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from geolens_api.models.analysis_citation import AnalysisCitation
    from geolens_api.models.analysis_claim import AnalysisClaim
    from geolens_api.models.analysis_entity import AnalysisEntity
    from geolens_api.models.analysis_run import AnalysisRun


class AnalysisResponse(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analysis_responses"
    __table_args__ = (
        UniqueConstraint(
            "analysis_run_id",
            "ordinal",
            name="uq_analysis_responses_analysis_run_id_ordinal",
        ),
    )

    analysis_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_response: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    token_usage: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    error: Mapped[dict[str, object] | None] = mapped_column(JSON)

    analysis_run: Mapped["AnalysisRun"] = relationship(back_populates="responses")
    citations: Mapped[list["AnalysisCitation"]] = relationship(
        back_populates="response",
        cascade="all, delete-orphan",
    )
    entities: Mapped[list["AnalysisEntity"]] = relationship(
        back_populates="response",
        cascade="all, delete-orphan",
    )
    claims: Mapped[list["AnalysisClaim"]] = relationship(
        back_populates="response",
        cascade="all, delete-orphan",
    )
