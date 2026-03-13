from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.clients.database.rss.rss_catalog_sync_database_client as sync_state_db_module


def test_get_rss_catalog_sync_state_returns_execute_result() -> None:
    db = Mock(spec=Session)
    execute_result = Mock()
    execute_result.scalar_one_or_none.return_value = SimpleNamespace(id=1)
    db.execute.return_value = execute_result

    result = sync_state_db_module.get_rss_catalog_sync_state(db)

    assert result.id == 1
    db.execute.assert_called_once()


def test_mark_rss_catalog_sync_success_updates_state_fields(monkeypatch) -> None:
    db = Mock(spec=Session)
    state = SimpleNamespace(
        last_applied_revision=None,
        last_seen_revision=None,
        last_sync_status="failed",
        last_sync_error="boom",
    )
    monkeypatch.setattr(
        sync_state_db_module,
        "get_or_create_rss_catalog_sync_state",
        lambda _db: state,
    )

    result = sync_state_db_module.mark_rss_catalog_sync_success(
        db,
        current_revision="rev-2",
    )

    assert result is state
    assert state.last_applied_revision == "rev-2"
    assert state.last_seen_revision == "rev-2"
    assert state.last_sync_status == "success"
    assert state.last_sync_error is None


def test_mark_rss_catalog_sync_failure_updates_state_fields(monkeypatch) -> None:
    db = Mock(spec=Session)
    state = SimpleNamespace(
        last_applied_revision="rev-1",
        last_seen_revision="rev-1",
        last_sync_status="success",
        last_sync_error=None,
    )
    monkeypatch.setattr(
        sync_state_db_module,
        "get_or_create_rss_catalog_sync_state",
        lambda _db: state,
    )

    result = sync_state_db_module.mark_rss_catalog_sync_failure(
        db,
        current_revision="rev-2",
        error_message="boom",
    )

    assert result is state
    assert state.last_applied_revision == "rev-1"
    assert state.last_seen_revision == "rev-2"
    assert state.last_sync_status == "failed"
    assert state.last_sync_error == "boom"
