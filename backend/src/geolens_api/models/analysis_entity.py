from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from geolens_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from geolens_api.models.analysis_response import AnalysisResponse


class AnalysisEntity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analysis_entities"
    __table_args__ = (
        UniqueConstraint(
            "response_id",
            "entity_key",
            name="uq_analysis_entities_response_id_entity_key",
        ),
    )

    response_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_responses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_key: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    matched_aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_mention_start: Mapped[int] = mapped_column(Integer, nullable=False)
    first_mention_relative: Mapped[float] = mapped_column(Float, nullable=False)
    position_bucket: Mapped[str] = mapped_column(String(16), nullable=False)
    mentions: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_rule_version: Mapped[str] = mapped_column(String(64), nullable=False)

    response: Mapped["AnalysisResponse"] = relationship(back_populates="entities")
