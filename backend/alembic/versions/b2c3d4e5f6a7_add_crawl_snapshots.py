"""Add crawl_snapshots for test-case-driven UI crawl (Phase 3)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-11 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crawl_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("flow_signature", sa.String(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("page_title", sa.String(), nullable=True),
        sa.Column("elements_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_crawl_snapshots_flow_signature"),
        "crawl_snapshots",
        ["flow_signature"],
        unique=False,
    )
    op.create_index(
        "ix_crawl_snapshots_flow_step",
        "crawl_snapshots",
        ["flow_signature", "step_index"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_crawl_snapshots_flow_step", table_name="crawl_snapshots")
    op.drop_index(op.f("ix_crawl_snapshots_flow_signature"), table_name="crawl_snapshots")
    op.drop_table("crawl_snapshots")
