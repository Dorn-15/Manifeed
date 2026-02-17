from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
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
        sa.Index(
            "idx_rss_feeds_status",
            "status",
            postgresql_where=sa.text("status = 'valid'"),
        ),
        sa.Index("idx_rss_feeds_company_id", "company_id"),
        sa.Index("idx_rss_feeds_company_id_section", "company_id", "section"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    company_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("rss_company.id", ondelete="SET NULL"),
        nullable=True,
    )
    section: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("true"),
    )
    status_enum = sa.Enum(
        "valid",
        "invalid",
        "unchecked",
        name="rss_feed_status",
    )
    status: Mapped[str] = mapped_column(
        status_enum,
        nullable=False,
        server_default=sa.text("'unchecked'"),
    )
    trust_score: Mapped[float] = mapped_column(
        sa.Float(),
        nullable=False,
        server_default=sa.text("0.5"),
    )
    language: Mapped[str | None] = mapped_column(sa.CHAR(2), nullable=True)
    icon_url: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    parsing_config: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    last_update: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
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

    company: Mapped["RssCompany | None"] = relationship(
        "RssCompany",
        back_populates="feeds",
        passive_deletes=True,
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
