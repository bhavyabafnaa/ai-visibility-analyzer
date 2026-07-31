"""Create the initial persistence schema.

Revision ID: 0001
Revises:
Create Date: 2026-07-30
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
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
    """Create project-management and job-tracking tables."""
    op.create_table(
        "projects",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_table(
        "sites",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_sites_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sites")),
        sa.UniqueConstraint("project_id", name=op.f("uq_sites_project_id")),
    )
    op.create_table(
        "competitors",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_competitors_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_competitors")),
    )
    op.create_index(
        op.f("ix_competitors_project_id"),
        "competitors",
        ["project_id"],
        unique=False,
    )
    op.create_table(
        "crawl_jobs",
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            name=op.f("fk_crawl_jobs_site_id_sites"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crawl_jobs")),
    )
    op.create_index(
        op.f("ix_crawl_jobs_site_id"),
        "crawl_jobs",
        ["site_id"],
        unique=False,
    )
    op.create_table(
        "analysis_runs",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("crawl_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["crawl_job_id"],
            ["crawl_jobs.id"],
            name=op.f("fk_analysis_runs_crawl_job_id_crawl_jobs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_analysis_runs_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_runs")),
    )
    op.create_index(
        op.f("ix_analysis_runs_crawl_job_id"),
        "analysis_runs",
        ["crawl_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analysis_runs_project_id"),
        "analysis_runs",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop all initial persistence tables."""
    op.drop_index(op.f("ix_analysis_runs_project_id"), table_name="analysis_runs")
    op.drop_index(op.f("ix_analysis_runs_crawl_job_id"), table_name="analysis_runs")
    op.drop_table("analysis_runs")
    op.drop_index(op.f("ix_crawl_jobs_site_id"), table_name="crawl_jobs")
    op.drop_table("crawl_jobs")
    op.drop_index(op.f("ix_competitors_project_id"), table_name="competitors")
    op.drop_table("competitors")
    op.drop_table("sites")
    op.drop_table("projects")
