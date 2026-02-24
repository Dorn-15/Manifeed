from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class RssFeedTag(Base):
    __tablename__ = "rss_feed_tags"
    __table_args__ = (
        sa.Index("idx_rss_feed_tags_tag_id", "tag_id"),
    )

    feed_id: Mapped[int] = mapped_column(
        sa.ForeignKey("rss_feeds.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        sa.ForeignKey("rss_tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
