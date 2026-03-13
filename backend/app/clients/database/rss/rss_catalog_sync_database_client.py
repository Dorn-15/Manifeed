from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rss import RssCatalogSyncState

_SYNC_STATE_ID = 1


def get_rss_catalog_sync_state(db: Session) -> RssCatalogSyncState | None:
    return db.execute(
        select(RssCatalogSyncState).where(RssCatalogSyncState.id == _SYNC_STATE_ID)
    ).scalar_one_or_none()


def get_or_create_rss_catalog_sync_state(db: Session) -> RssCatalogSyncState:
    state = get_rss_catalog_sync_state(db)
    if state is not None:
        return state

    state = RssCatalogSyncState(id=_SYNC_STATE_ID)
    db.add(state)
    db.flush()
    return state


def mark_rss_catalog_sync_success(
    db: Session,
    *,
    current_revision: str | None,
) -> RssCatalogSyncState:
    state = get_or_create_rss_catalog_sync_state(db)
    state.last_applied_revision = current_revision
    state.last_seen_revision = current_revision
    state.last_sync_status = "success"
    state.last_sync_error = None
    return state


def mark_rss_catalog_sync_failure(
    db: Session,
    *,
    current_revision: str | None,
    error_message: str,
) -> RssCatalogSyncState:
    state = get_or_create_rss_catalog_sync_state(db)
    state.last_seen_revision = current_revision
    state.last_sync_status = "failed"
    state.last_sync_error = error_message
    return state
