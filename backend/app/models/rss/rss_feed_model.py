from __future__ import annotations

from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RssFeed(Base):
    __tablename__ = "rss_feeds"
    __table_args__ = (
        sa.UniqueConstraint("url", name="uq_rss_feeds_url"),
        sa.CheckConstraint(
            "trust_score >= 0.0 AND trust_score <= 1.0",
            name="ck_rss_feeds_trust_score",
        ),
        sa.Index(
            "idx_rss_feeds_enabled",
            "enabled",
            postgresql_where=sa.text("enabled = true"),
        ),
        sa.CheckConstraint(
            "fetchprotection >= 0 AND fetchprotection <= 3",
            name="ck_rss_feeds_fetchprotection",
        ),
        sa.Index("idx_rss_feeds_fetchprotection", "fetchprotection"),
        sa.Index("idx_rss_feeds_company_id", "company_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    section: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("true"),
    )
    trust_score: Mapped[float] = mapped_column(
        sa.Float(),
        nullable=False,
        server_default=sa.text("0.5"),
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
    company_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("rss_company.id", ondelete="SET NULL"),
        nullable=True,
    )

    company: Mapped["RssCompany | None"] = relationship(
        "RssCompany",
        back_populates="feeds",
    )
    tags: Mapped[list["RssTag"]] = relationship(
        "RssTag",
        secondary="rss_feed_tags",
        back_populates="feeds",
    )
    source_links: Mapped[list["RssSourceFeed"]] = relationship(
        "RssSourceFeed",
        back_populates="feed",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sources: Mapped[list["RssSource"]] = relationship(
        "RssSource",
        secondary="rss_source_feeds",
        back_populates="feeds",
        viewonly=True,
    )
