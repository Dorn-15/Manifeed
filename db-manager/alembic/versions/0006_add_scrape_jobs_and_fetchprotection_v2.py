"""add scrape jobs tables and enforce fetchprotection range 0..2

Revision ID: 0006_scrape_jobs_v2
Revises: 0005_restore_partitioning
Create Date: 2026-02-26 14:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0006_scrape_jobs_v2"
down_revision = "0005_restore_partitioning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE rss_company SET fetchprotection = 2 WHERE fetchprotection > 2")
    op.execute("UPDATE feeds_scraping SET fetchprotection = 2 WHERE fetchprotection > 2")

    op.drop_constraint("ck_rss_company_fetchprotection", "rss_company", type_="check")
    op.create_check_constraint(
        "ck_rss_company_fetchprotection",
        "rss_company",
        "fetchprotection >= 0 AND fetchprotection <= 2",
    )

    op.drop_constraint("ck_feeds_scraping_fetchprotection", "feeds_scraping", type_="check")
    op.create_check_constraint(
        "ck_feeds_scraping_fetchprotection",
        "feeds_scraping",
        "fetchprotection >= 0 AND fetchprotection <= 2",
    )

    op.create_table(
        "rss_scrape_jobs",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("ingest", sa.Boolean(), nullable=False),
        sa.Column("requested_by", sa.String(length=100), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("feed_count", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=40),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("feed_count >= 0", name="ck_rss_scrape_jobs_feed_count"),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'completed_with_errors', 'failed')",
            name="ck_rss_scrape_jobs_status",
        ),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index(
        "idx_rss_scrape_jobs_requested_at",
        "rss_scrape_jobs",
        ["requested_at"],
        unique=False,
    )

    op.create_table(
        "rss_scrape_job_feeds",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("feed_id", sa.Integer(), nullable=False),
        sa.Column("feed_url", sa.String(length=500), nullable=False),
        sa.Column("last_db_article_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["feed_id"], ["rss_feeds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["rss_scrape_jobs.job_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id", "feed_id"),
    )
    op.create_index(
        "idx_rss_scrape_job_feeds_feed_id",
        "rss_scrape_job_feeds",
        ["feed_id"],
        unique=False,
    )

    op.create_table(
        "rss_scrape_job_results",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("feed_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("queue_kind", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("fetchprotection", sa.SmallInteger(), nullable=True),
        sa.Column("new_etag", sa.String(length=255), nullable=True),
        sa.Column("new_last_update", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('success', 'not_modified', 'error')",
            name="ck_rss_scrape_job_results_status",
        ),
        sa.CheckConstraint(
            "queue_kind IN ('check', 'ingest', 'error')",
            name="ck_rss_scrape_job_results_queue_kind",
        ),
        sa.ForeignKeyConstraint(["feed_id"], ["rss_feeds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["rss_scrape_jobs.job_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id", "feed_id"),
    )


def downgrade() -> None:
    op.drop_table("rss_scrape_job_results")
    op.drop_index("idx_rss_scrape_job_feeds_feed_id", table_name="rss_scrape_job_feeds")
    op.drop_table("rss_scrape_job_feeds")
    op.drop_index("idx_rss_scrape_jobs_requested_at", table_name="rss_scrape_jobs")
    op.drop_table("rss_scrape_jobs")

    op.drop_constraint("ck_feeds_scraping_fetchprotection", "feeds_scraping", type_="check")
    op.create_check_constraint(
        "ck_feeds_scraping_fetchprotection",
        "feeds_scraping",
        "fetchprotection >= 0 AND fetchprotection <= 3",
    )

    op.drop_constraint("ck_rss_company_fetchprotection", "rss_company", type_="check")
    op.create_check_constraint(
        "ck_rss_company_fetchprotection",
        "rss_company",
        "fetchprotection >= 0 AND fetchprotection <= 3",
    )
