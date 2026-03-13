from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RssSourceContent(Base):
    __tablename__ = "rss_source_contents"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["rss_sources.id"],
            ondelete="CASCADE",
        ),
        sa.Index("idx_rss_source_contents_ingested_at", "ingested_at"),
        {
            "postgresql_partition_by": "RANGE (ingested_at)",
        },
    )

    source_id: Mapped[int] = mapped_column(primary_key=True)
    ingested_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), primary_key=True)
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    author: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    image_url: Mapped[str | None] = mapped_column(sa.String(1000), nullable=True)

    source: Mapped["RssSource"] = relationship("RssSource", back_populates="content")
