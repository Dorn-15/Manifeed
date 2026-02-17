"""add rss_sources and rss_source_feeds tables

Revision ID: 0003_add_rss_sources_and_links
Revises: 0002_add_enabled_to_rss_company
Create Date: 2026-02-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0003_add_rss_sources_and_links"
down_revision = "0002_add_enabled_to_rss_company"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rss_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.CHAR(length=2), nullable=True),
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("url", name="uq_rss_sources_url"),
    )
    op.create_index("idx_rss_sources_language", "rss_sources", ["language"])
    op.create_index("idx_rss_sources_published_at", "rss_sources", ["published_at"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_rss_sources_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.updated_at = now();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_rss_sources_updated_at
        BEFORE UPDATE ON rss_sources
        FOR EACH ROW
        EXECUTE FUNCTION set_rss_sources_updated_at();
        """
    )

    op.create_table(
        "rss_source_feeds",
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("feed_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["rss_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["feed_id"], ["rss_feeds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_id", "feed_id"),
    )
    op.create_index("idx_rss_source_feeds_source_id", "rss_source_feeds", ["source_id"])
    op.create_index("idx_rss_source_feeds_feed_id", "rss_source_feeds", ["feed_id"])


def downgrade() -> None:
    op.drop_index("idx_rss_source_feeds_feed_id", table_name="rss_source_feeds")
    op.drop_index("idx_rss_source_feeds_source_id", table_name="rss_source_feeds")
    op.drop_table("rss_source_feeds")

    op.execute("DROP TRIGGER IF EXISTS trg_rss_sources_updated_at ON rss_sources")
    op.execute("DROP FUNCTION IF EXISTS set_rss_sources_updated_at")

    op.drop_index("idx_rss_sources_published_at", table_name="rss_sources")
    op.drop_index("idx_rss_sources_language", table_name="rss_sources")
    op.drop_table("rss_sources")
