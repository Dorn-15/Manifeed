from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RssCompany(Base):
    __tablename__ = "rss_company"
    __table_args__ = (
        sa.UniqueConstraint("name", name="uq_rss_company_name"),
        sa.Index("idx_rss_company_name", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(50), nullable=False)

    feeds: Mapped[list["RssFeed"]] = relationship(
        "RssFeed",
        back_populates="company",
        passive_deletes=True,
    )
