"""add enabled column to rss_company

Revision ID: 0002_add_enabled_to_rss_company
Revises: 0001_initial_schema
Create Date: 2026-02-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0002_add_enabled_to_rss_company"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rss_company",
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("rss_company", "enabled")
