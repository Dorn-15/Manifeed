"""create feeds scraping table

Revision ID: 0003_create_feeds_scraping_table
Revises: 0002_add_rss_feed_etag
Create Date: 2026-02-25 15:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0003_create_feeds_scraping_table"
down_revision = "0002_add_rss_feed_etag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feeds_scraping",
        sa.Column("feed_id", sa.Integer(), nullable=False),
        sa.Column(
            "fetchprotection",
            sa.SmallInteger(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("last_update", sa.DateTime(timezone=True), nullable=True),
        sa.Column("etag", sa.String(length=255), nullable=True),
        sa.Column(
            "error_nbr",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "fetchprotection >= 0 AND fetchprotection <= 3",
            name="ck_feeds_scraping_fetchprotection",
        ),
        sa.CheckConstraint(
            "error_nbr >= 0",
            name="ck_feeds_scraping_error_nbr",
        ),
        sa.ForeignKeyConstraint(["feed_id"], ["rss_feeds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("feed_id"),
    )
    op.create_index(
        "idx_feeds_scraping_fetchprotection",
        "feeds_scraping",
        ["fetchprotection"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO feeds_scraping (feed_id, fetchprotection, last_update, etag, error_nbr, error_msg)
        SELECT id, fetchprotection, last_update, etag, 0, NULL
        FROM rss_feeds
        """
    )

    op.drop_index("idx_rss_feeds_fetchprotection", table_name="rss_feeds")
    op.drop_constraint("ck_rss_feeds_fetchprotection", "rss_feeds", type_="check")
    op.drop_column("rss_feeds", "last_update")
    op.drop_column("rss_feeds", "etag")
    op.drop_column("rss_feeds", "fetchprotection")


def downgrade() -> None:
    op.add_column(
        "rss_feeds",
        sa.Column(
            "fetchprotection",
            sa.SmallInteger(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.add_column(
        "rss_feeds",
        sa.Column("etag", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "rss_feeds",
        sa.Column("last_update", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        """
        UPDATE rss_feeds AS feed
        SET
            fetchprotection = scraping.fetchprotection,
            etag = scraping.etag,
            last_update = scraping.last_update
        FROM feeds_scraping AS scraping
        WHERE scraping.feed_id = feed.id
        """
    )

    op.create_check_constraint(
        "ck_rss_feeds_fetchprotection",
        "rss_feeds",
        "fetchprotection >= 0 AND fetchprotection <= 3",
    )
    op.create_index(
        "idx_rss_feeds_fetchprotection",
        "rss_feeds",
        ["fetchprotection"],
        unique=False,
    )

    op.drop_index("idx_feeds_scraping_fetchprotection", table_name="feeds_scraping")
    op.drop_table("feeds_scraping")
