"""Add ui_elements table for semantic element registry (Katalon/KaneAI-style)

Revision ID: f5e6f7a8b9c0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "f5e6f7a8b9c0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ui_elements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("app_key", sa.String(64), nullable=False),
        sa.Column("page_pattern", sa.String(256), nullable=False),
        sa.Column("intent", sa.String(64), nullable=False),
        sa.Column("element_name", sa.String(256), nullable=True),
        sa.Column("selectors", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ui_elements_app_key"),
        "ui_elements",
        ["app_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ui_elements_page_pattern"),
        "ui_elements",
        ["page_pattern"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ui_elements_intent"),
        "ui_elements",
        ["intent"],
        unique=False,
    )
    op.create_index(
        "ix_ui_elements_app_page_intent",
        "ui_elements",
        ["app_key", "page_pattern", "intent"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_ui_elements_app_page_intent", table_name="ui_elements")
    op.drop_index(op.f("ix_ui_elements_intent"), table_name="ui_elements")
    op.drop_index(op.f("ix_ui_elements_page_pattern"), table_name="ui_elements")
    op.drop_index(op.f("ix_ui_elements_app_key"), table_name="ui_elements")
    op.drop_table("ui_elements")
