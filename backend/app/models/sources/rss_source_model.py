from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RssSource(Base):
    __tablename__ = "rss_sources"
    __table_args__ = (
        sa.UniqueConstraint(
            "url",
            "published_at",
            name="uq_rss_sources_url_published_at",
        ),
        sa.Index("idx_rss_sources_published_at", "published_at"),
        {
            "postgresql_partition_by": "RANGE (published_at)",
        },
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    author: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    url: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        primary_key=True,
        nullable=False,
        server_default=sa.func.now(),
    )
    image_url: Mapped[str | None] = mapped_column(sa.String(1000), nullable=True)

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
