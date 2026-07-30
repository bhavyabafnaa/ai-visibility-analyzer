"""Add crawl page and error persistence.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-30
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
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
    op.add_column("crawl_jobs", sa.Column("celery_task_id", sa.String(length=255)))
    op.add_column(
        "crawl_jobs",
        sa.Column("page_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "crawl_jobs",
        sa.Column("error_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "crawl_pages",
        sa.Column("crawl_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048)),
        sa.Column("title", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("headings", sa.JSON(), nullable=False),
        sa.Column("main_text", sa.Text(), nullable=False),
        sa.Column("structured_data", sa.JSON(), nullable=False),
        sa.Column("internal_links", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=255)),
        sa.Column("response_size", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["crawl_job_id"],
            ["crawl_jobs.id"],
            name=op.f("fk_crawl_pages_crawl_job_id_crawl_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crawl_pages")),
        sa.UniqueConstraint(
            "crawl_job_id",
            "url",
            name="uq_crawl_pages_crawl_job_id_url",
        ),
    )
    op.create_index(
        op.f("ix_crawl_pages_crawl_job_id"),
        "crawl_pages",
        ["crawl_job_id"],
    )
    op.create_index(
        op.f("ix_crawl_pages_content_hash"),
        "crawl_pages",
        ["content_hash"],
    )
    op.create_table(
        "crawl_errors",
        sa.Column("crawl_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.String(length=2048)),
        sa.Column("depth", sa.Integer()),
        sa.Column("stage", sa.String(length=50), nullable=False),
        sa.Column("error_type", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["crawl_job_id"],
            ["crawl_jobs.id"],
            name=op.f("fk_crawl_errors_crawl_job_id_crawl_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crawl_errors")),
    )
    op.create_index(
        op.f("ix_crawl_errors_crawl_job_id"),
        "crawl_errors",
        ["crawl_job_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_crawl_errors_crawl_job_id"), table_name="crawl_errors")
    op.drop_table("crawl_errors")
    op.drop_index(op.f("ix_crawl_pages_content_hash"), table_name="crawl_pages")
    op.drop_index(op.f("ix_crawl_pages_crawl_job_id"), table_name="crawl_pages")
    op.drop_table("crawl_pages")
    op.drop_column("crawl_jobs", "error_count")
    op.drop_column("crawl_jobs", "page_count")
    op.drop_column("crawl_jobs", "celery_task_id")
