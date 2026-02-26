"""add etag to rss feeds

Revision ID: 0002_add_rss_feed_etag
Revises: 0001_initial_schema
Create Date: 2026-02-25 13:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0002_add_rss_feed_etag"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rss_feeds", sa.Column("etag", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("rss_feeds", "etag")
