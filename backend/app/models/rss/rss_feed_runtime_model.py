from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RssFeedRuntime(Base):
    __tablename__ = "rss_feed_runtime"
    __table_args__ = (
        sa.CheckConstraint(
            "last_status IN ('pending', 'success', 'not_modified', 'error')",
            name="ck_rss_feed_runtime_last_status",
        ),
        sa.CheckConstraint(
            "consecutive_error_count >= 0",
            name="ck_rss_feed_runtime_consecutive_error_count",
        ),
        sa.Index("idx_rss_feed_runtime_last_status", "last_status"),
        sa.Index("idx_rss_feed_runtime_last_success_at", "last_success_at"),
        sa.Index(
            "idx_rss_feed_runtime_last_db_article_published_at",
            "last_db_article_published_at",
        ),
    )

    feed_id: Mapped[int] = mapped_column(
        sa.ForeignKey("rss_feeds.id", ondelete="CASCADE"),
        primary_key=True,
    )
    last_scraped_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    last_status: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        server_default=sa.text("'pending'"),
    )
    etag: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    last_feed_updated_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    last_db_article_published_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    consecutive_error_count: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    )
    last_error_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    feed: Mapped["RssFeed"] = relationship("RssFeed", back_populates="runtime")
