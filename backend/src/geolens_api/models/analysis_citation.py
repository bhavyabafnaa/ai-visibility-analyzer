from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from geolens_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from geolens_api.models.analysis_response import AnalysisResponse


class AnalysisCitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analysis_citations"
    __table_args__ = (
        UniqueConstraint(
            "response_id",
            "ordinal",
            name="uq_analysis_citations_response_id_ordinal",
        ),
    )

    response_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_responses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_domain: Mapped[str | None] = mapped_column(String(255), index=True)
    title: Mapped[str | None] = mapped_column(Text)
    start_index: Mapped[int | None] = mapped_column(Integer)
    end_index: Mapped[int | None] = mapped_column(Integer)
    cited_text: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[str | None] = mapped_column(String(255))
    normalization_rule_version: Mapped[str] = mapped_column(String(64), nullable=False)

    response: Mapped["AnalysisResponse"] = relationship(back_populates="citations")
