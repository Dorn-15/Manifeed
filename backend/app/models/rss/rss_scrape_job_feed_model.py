from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RssScrapeJobFeed(Base):
    __tablename__ = "rss_scrape_job_feeds"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["rss_scrape_jobs.job_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["feed_id"],
            ["rss_feeds.id"],
            ondelete="CASCADE",
        ),
        sa.Index("idx_rss_scrape_job_feeds_feed_id", "feed_id"),
    )

    job_id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    feed_id: Mapped[int] = mapped_column(primary_key=True)
    feed_url: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    last_db_article_published_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

    job: Mapped["RssScrapeJob"] = relationship(
        "RssScrapeJob",
        back_populates="feeds",
    )
