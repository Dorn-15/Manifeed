from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RssSource(Base):
    __tablename__ = "rss_sources"
    __table_args__ = (
        sa.UniqueConstraint("url", name="uq_rss_sources_url"),
        sa.Index("idx_rss_sources_language", "language"),
        sa.Index("idx_rss_sources_published_at", "published_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    url: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    language: Mapped[str | None] = mapped_column(sa.CHAR(2), nullable=True)
    image_url: Mapped[str | None] = mapped_column(sa.String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    feed_links: Mapped[list["RssSourceFeed"]] = relationship(
        "RssSourceFeed",
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    feeds: Mapped[list["RssFeed"]] = relationship(
        "RssFeed",
        secondary="rss_source_feeds",
        back_populates="sources",
        viewonly=True,
    )
