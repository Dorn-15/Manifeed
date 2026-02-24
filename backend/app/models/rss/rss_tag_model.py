from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RssTag(Base):
    __tablename__ = "rss_tags"
    __table_args__ = (
        sa.UniqueConstraint("name", name="uq_rss_tags_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(50), nullable=False)

    feeds: Mapped[list["RssFeed"]] = relationship(
        "RssFeed",
        secondary="rss_feed_tags",
        back_populates="tags",
    )
