from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RssScrapeJobResult(Base):
    __tablename__ = "rss_scrape_job_results"
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
        sa.CheckConstraint(
            "status IN ('success', 'not_modified', 'error')",
            name="ck_rss_scrape_job_results_status",
        ),
        sa.CheckConstraint(
            "queue_kind IN ('check', 'ingest', 'error')",
            name="ck_rss_scrape_job_results_queue_kind",
        ),
    )

    job_id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    feed_id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    queue_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    error_message: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    fetchprotection: Mapped[int | None] = mapped_column(sa.SmallInteger(), nullable=True)
    new_etag: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    new_last_update: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    processed_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    job: Mapped["RssScrapeJob"] = relationship(
        "RssScrapeJob",
        back_populates="results",
    )
