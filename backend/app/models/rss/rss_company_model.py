from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RssCompany(Base):
    __tablename__ = "rss_company"
    __table_args__ = (
        sa.UniqueConstraint("name", name="uq_rss_company_name"),
        sa.CheckConstraint(
            "fetchprotection >= 0 AND fetchprotection <= 2",
            name="ck_rss_company_fetchprotection",
        ),
        sa.Index("idx_rss_company_country", "country"),
        sa.Index("idx_rss_company_language", "language"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    host: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    icon_url: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    country: Mapped[str | None] = mapped_column(sa.CHAR(2), nullable=True)
    language: Mapped[str | None] = mapped_column(sa.CHAR(2), nullable=True)
    fetchprotection: Mapped[int] = mapped_column(
        sa.SmallInteger(),
        nullable=False,
        server_default=sa.text("1"),
    )
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("true"),
    )

    feeds: Mapped[list["RssFeed"]] = relationship(
        "RssFeed",
        back_populates="company",
        passive_deletes=True,
    )
