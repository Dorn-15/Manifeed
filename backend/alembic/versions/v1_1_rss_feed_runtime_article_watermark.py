"""add rss feed runtime article watermark

Revision ID: v1_1_rss_feed_runtime_wm
Revises: v1_initialization
Create Date: 2026-03-11 00:00:01.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "v1_1_rss_feed_runtime_wm"
down_revision = "v1_initialization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rss_feed_runtime",
        sa.Column("last_db_article_published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_rss_feed_runtime_last_db_article_published_at",
        "rss_feed_runtime",
        ["last_db_article_published_at"],
        unique=False,
    )
    op.execute(
        """
        UPDATE rss_feed_runtime AS runtime
        SET last_db_article_published_at = derived.last_db_article_published_at
        FROM (
            SELECT
                source_feed.feed_id,
                MAX(source.published_at) AS last_db_article_published_at
            FROM rss_source_feeds AS source_feed
            JOIN rss_sources AS source
                ON source.id = source_feed.source_id
            GROUP BY source_feed.feed_id
        ) AS derived
        WHERE derived.feed_id = runtime.feed_id
        """
    )


def downgrade() -> None:
    op.drop_index(
        "idx_rss_feed_runtime_last_db_article_published_at",
        table_name="rss_feed_runtime",
    )
    op.drop_column("rss_feed_runtime", "last_db_article_published_at")
