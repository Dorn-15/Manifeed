from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RssFeedScraping(Base):
    __tablename__ = "feeds_scraping"
    __table_args__ = (
        sa.CheckConstraint(
            "fetchprotection >= 0 AND fetchprotection <= 2",
            name="ck_feeds_scraping_fetchprotection",
        ),
        sa.CheckConstraint(
            "error_nbr >= 0",
            name="ck_feeds_scraping_error_nbr",
        ),
        sa.Index("idx_feeds_scraping_fetchprotection", "fetchprotection"),
    )

    feed_id: Mapped[int] = mapped_column(
        sa.ForeignKey("rss_feeds.id", ondelete="CASCADE"),
        primary_key=True,
    )
    fetchprotection: Mapped[int] = mapped_column(
        sa.SmallInteger(),
        nullable=False,
        server_default=sa.text("1"),
    )
    last_update: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    etag: Mapped[str | None] = mapped_column(
        sa.String(255),
        nullable=True,
    )
    error_nbr: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    )
    error_msg: Mapped[str | None] = mapped_column(
        sa.Text(),
        nullable=True,
    )

    feed: Mapped["RssFeed"] = relationship(
        "RssFeed",
        back_populates="scraping",
    )
