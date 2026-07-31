"""Persist deterministic measurements and model-assisted claim assessments.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-30
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> tuple[sa.Column[datetime], sa.Column[datetime]]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    empty_json = sa.text("'[]'::json")
    op.add_column(
        "projects",
        sa.Column("aliases", sa.JSON(), server_default=empty_json, nullable=False),
    )
    op.add_column(
        "competitors",
        sa.Column("aliases", sa.JSON(), server_default=empty_json, nullable=False),
    )

    op.create_table(
        "analysis_responses",
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model_identifier", sa.String(length=255), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("raw_response", sa.JSON(), nullable=False),
        sa.Column("token_usage", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("error", sa.JSON()),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_analysis_responses_analysis_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_responses")),
        sa.UniqueConstraint(
            "analysis_run_id",
            "ordinal",
            name="uq_analysis_responses_analysis_run_id_ordinal",
        ),
    )
    op.create_index(
        op.f("ix_analysis_responses_analysis_run_id"),
        "analysis_responses",
        ["analysis_run_id"],
    )

    op.create_table(
        "analysis_scores",
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("numerator", sa.Float(), nullable=False),
        sa.Column("denominator", sa.Float(), nullable=False),
        sa.Column("value", sa.Float()),
        sa.Column("percentage", sa.Float()),
        sa.Column("is_defined", sa.Boolean(), nullable=False),
        sa.Column("method", sa.String(length=64), nullable=False),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.Column("is_objective_truth", sa.Boolean()),
        sa.Column("disclaimer", sa.Text()),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_analysis_scores_analysis_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_scores")),
        sa.UniqueConstraint(
            "analysis_run_id",
            "name",
            name="uq_analysis_scores_analysis_run_id_name",
        ),
    )
    op.create_index(
        op.f("ix_analysis_scores_analysis_run_id"),
        "analysis_scores",
        ["analysis_run_id"],
    )

    op.create_table(
        "analysis_citations",
        sa.Column("response_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("normalized_domain", sa.String(length=255)),
        sa.Column("title", sa.Text()),
        sa.Column("start_index", sa.Integer()),
        sa.Column("end_index", sa.Integer()),
        sa.Column("cited_text", sa.Text()),
        sa.Column("published_at", sa.String(length=255)),
        sa.Column("normalization_rule_version", sa.String(length=64), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["response_id"],
            ["analysis_responses.id"],
            name=op.f("fk_analysis_citations_response_id_analysis_responses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_citations")),
        sa.UniqueConstraint(
            "response_id",
            "ordinal",
            name="uq_analysis_citations_response_id_ordinal",
        ),
    )
    op.create_index(
        op.f("ix_analysis_citations_response_id"),
        "analysis_citations",
        ["response_id"],
    )
    op.create_index(
        op.f("ix_analysis_citations_normalized_domain"),
        "analysis_citations",
        ["normalized_domain"],
    )

    op.create_table(
        "analysis_entities",
        sa.Column("response_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("matched_aliases", sa.JSON(), nullable=False),
        sa.Column("mention_count", sa.Integer(), nullable=False),
        sa.Column("first_mention_start", sa.Integer(), nullable=False),
        sa.Column("first_mention_relative", sa.Float(), nullable=False),
        sa.Column("position_bucket", sa.String(length=16), nullable=False),
        sa.Column("mentions", sa.JSON(), nullable=False),
        sa.Column("extraction_method", sa.String(length=64), nullable=False),
        sa.Column("extraction_rule_version", sa.String(length=64), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["response_id"],
            ["analysis_responses.id"],
            name=op.f("fk_analysis_entities_response_id_analysis_responses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_entities")),
        sa.UniqueConstraint(
            "response_id",
            "entity_key",
            name="uq_analysis_entities_response_id_entity_key",
        ),
    )
    op.create_index(
        op.f("ix_analysis_entities_response_id"),
        "analysis_entities",
        ["response_id"],
    )

    op.create_table(
        "analysis_claims",
        sa.Column("response_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("start_index", sa.Integer(), nullable=False),
        sa.Column("end_index", sa.Integer(), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("classifier", sa.String(length=100), nullable=False),
        sa.Column("model_identifier", sa.String(length=255)),
        sa.Column("segmentation_rule_version", sa.String(length=64), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["response_id"],
            ["analysis_responses.id"],
            name=op.f("fk_analysis_claims_response_id_analysis_responses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_claims")),
        sa.UniqueConstraint(
            "response_id",
            "ordinal",
            name="uq_analysis_claims_response_id_ordinal",
        ),
    )
    op.create_index(
        op.f("ix_analysis_claims_response_id"),
        "analysis_claims",
        ["response_id"],
    )

    op.create_table(
        "claim_evidence",
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_reference", sa.String(length=512), nullable=False),
        sa.Column("url", sa.String(length=2048)),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("retrieval_rule_version", sa.String(length=64), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["analysis_claims.id"],
            name=op.f("fk_claim_evidence_claim_id_analysis_claims"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_claim_evidence")),
        sa.UniqueConstraint(
            "claim_id",
            "source_reference",
            name="uq_claim_evidence_claim_id_source_reference",
        ),
    )
    op.create_index(
        op.f("ix_claim_evidence_claim_id"),
        "claim_evidence",
        ["claim_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_claim_evidence_claim_id"), table_name="claim_evidence")
    op.drop_table("claim_evidence")
    op.drop_index(op.f("ix_analysis_claims_response_id"), table_name="analysis_claims")
    op.drop_table("analysis_claims")
    op.drop_index(op.f("ix_analysis_entities_response_id"), table_name="analysis_entities")
    op.drop_table("analysis_entities")
    op.drop_index(
        op.f("ix_analysis_citations_normalized_domain"),
        table_name="analysis_citations",
    )
    op.drop_index(op.f("ix_analysis_citations_response_id"), table_name="analysis_citations")
    op.drop_table("analysis_citations")
    op.drop_index(op.f("ix_analysis_scores_analysis_run_id"), table_name="analysis_scores")
    op.drop_table("analysis_scores")
    op.drop_index(
        op.f("ix_analysis_responses_analysis_run_id"),
        table_name="analysis_responses",
    )
    op.drop_table("analysis_responses")
    op.drop_column("competitors", "aliases")
    op.drop_column("projects", "aliases")
