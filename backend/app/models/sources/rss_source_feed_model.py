from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RssSourceFeed(Base):
    __tablename__ = "rss_source_feeds"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["source_id", "published_at"],
            ["rss_sources.id", "rss_sources.published_at"],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["feed_id"],
            ["rss_feeds.id"],
            ondelete="CASCADE",
        ),
        sa.Index(
            "idx_rss_source_feeds_source_id_published_at",
            "source_id",
            "published_at",
        ),
        sa.Index("idx_rss_source_feeds_feed_id", "feed_id"),
        sa.Index("idx_rss_source_feeds_published_at", "published_at"),
        {
            "postgresql_partition_by": "RANGE (published_at)",
        },
    )

    source_id: Mapped[int] = mapped_column(primary_key=True)
    feed_id: Mapped[int] = mapped_column(primary_key=True)
    published_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        primary_key=True,
        nullable=False,
    )

    source: Mapped["RssSource"] = relationship("RssSource", back_populates="feed_links")
    feed: Mapped["RssFeed"] = relationship("RssFeed", back_populates="source_links")
