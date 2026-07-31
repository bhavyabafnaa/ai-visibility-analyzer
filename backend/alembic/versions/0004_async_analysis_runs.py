"""Persist queued analysis execution configuration.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    empty_json = sa.text("'[]'::json")
    op.add_column(
        "analysis_runs",
        sa.Column("celery_task_id", sa.String(length=255)),
    )
    op.add_column(
        "analysis_runs",
        sa.Column(
            "provider_configurations",
            sa.JSON(),
            server_default=empty_json,
            nullable=False,
        ),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("prompts", sa.JSON(), server_default=empty_json, nullable=False),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("claim_classifier_configuration", sa.JSON()),
    )


def downgrade() -> None:
    op.drop_column("analysis_runs", "claim_classifier_configuration")
    op.drop_column("analysis_runs", "prompts")
    op.drop_column("analysis_runs", "provider_configurations")
    op.drop_column("analysis_runs", "celery_task_id")
