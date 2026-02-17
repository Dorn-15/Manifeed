from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RssSourceFeed(Base):
    __tablename__ = "rss_source_feeds"
    __table_args__ = (
        sa.Index("idx_rss_source_feeds_source_id", "source_id"),
        sa.Index("idx_rss_source_feeds_feed_id", "feed_id"),
    )

    source_id: Mapped[int] = mapped_column(
        sa.ForeignKey("rss_sources.id", ondelete="CASCADE"),
        primary_key=True,
    )
    feed_id: Mapped[int] = mapped_column(
        sa.ForeignKey("rss_feeds.id", ondelete="CASCADE"),
        primary_key=True,
    )

    source: Mapped["RssSource"] = relationship("RssSource", back_populates="feed_links")
    feed: Mapped["RssFeed"] = relationship("RssFeed", back_populates="source_links")
