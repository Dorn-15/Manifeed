from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class RssCatalogSyncState(Base):
    __tablename__ = "rss_catalog_sync_state"
    __table_args__ = (
        sa.CheckConstraint(
            "last_sync_status IN ('success', 'failed')",
            name="ck_rss_catalog_sync_state_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    last_applied_revision: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    last_seen_revision: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    last_sync_status: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        server_default=sa.text("'success'"),
    )
    last_sync_error: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
