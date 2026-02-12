"""Change ui_testcases.script from text to JSONB

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert existing text scripts to JSONB strings.
    # New writes will store an object: {language, content}
    op.alter_column(
        "ui_testcases",
        "script",
        existing_type=sa.Text(),
        type_=postgresql.JSONB(),
        postgresql_using="to_jsonb(script)",
        existing_nullable=True,
    )


def downgrade() -> None:
    # Convert JSONB back to text (objects become JSON text).
    op.alter_column(
        "ui_testcases",
        "script",
        existing_type=postgresql.JSONB(),
        type_=sa.Text(),
        postgresql_using="script::text",
        existing_nullable=True,
    )

