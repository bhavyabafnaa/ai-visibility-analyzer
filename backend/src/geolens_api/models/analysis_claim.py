from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from geolens_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from geolens_api.models.analysis_response import AnalysisResponse


class AnalysisClaim(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analysis_claims"
    __table_args__ = (
        UniqueConstraint(
            "response_id",
            "ordinal",
            name="uq_analysis_claims_response_id_ordinal",
        ),
    )

    response_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_responses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    start_index: Mapped[int] = mapped_column(Integer, nullable=False)
    end_index: Mapped[int] = mapped_column(Integer, nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    classifier: Mapped[str] = mapped_column(String(100), nullable=False)
    model_identifier: Mapped[str | None] = mapped_column(String(255))
    segmentation_rule_version: Mapped[str] = mapped_column(String(64), nullable=False)

    response: Mapped["AnalysisResponse"] = relationship(back_populates="claims")
    evidence: Mapped[list["ClaimEvidence"]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
    )


class ClaimEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "claim_evidence"
    __table_args__ = (
        UniqueConstraint(
            "claim_id",
            "source_reference",
            name="uq_claim_evidence_claim_id_source_reference",
        ),
    )

    claim_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048))
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    retrieval_rule_version: Mapped[str] = mapped_column(String(64), nullable=False)

    claim: Mapped["AnalysisClaim"] = relationship(back_populates="evidence")
