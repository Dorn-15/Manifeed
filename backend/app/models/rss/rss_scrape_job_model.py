from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RssScrapeJob(Base):
    __tablename__ = "rss_scrape_jobs"
    __table_args__ = (
        sa.CheckConstraint("feed_count >= 0", name="ck_rss_scrape_jobs_feed_count"),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'completed_with_errors', 'failed')",
            name="ck_rss_scrape_jobs_status",
        ),
        sa.Index("idx_rss_scrape_jobs_requested_at", "requested_at"),
    )

    job_id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    ingest: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False)
    requested_by: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
    )
    feed_count: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(40),
        nullable=False,
        server_default=sa.text("'queued'"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    feeds: Mapped[list["RssScrapeJobFeed"]] = relationship(
        "RssScrapeJobFeed",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    results: Mapped[list["RssScrapeJobResult"]] = relationship(
        "RssScrapeJobResult",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
