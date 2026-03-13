from datetime import datetime, timezone
from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.services.internal.queue_monitoring_service as queue_monitoring_service_module
from app.clients.database.worker_queue_db_client import TaskQueueState, WorkerHeartbeatRead


def test_get_queues_overview_builds_local_payload(monkeypatch) -> None:
    db = Mock(spec=Session)
    generated_at = datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        queue_monitoring_service_module,
        "_resolve_threshold_ms",
        lambda env_name, default_value: default_value,
    )
    monkeypatch.setattr(
        queue_monitoring_service_module,
        "get_task_queue_state",
        lambda _db, *, task_kind: TaskQueueState(
            pending=3 if task_kind == "rss_scrape" else 0,
            processing=1 if task_kind == "rss_scrape" else 0,
            completed=0,
            failed=0,
            total=4 if task_kind == "rss_scrape" else 0,
            last_task_id=12 if task_kind == "rss_scrape" else None,
        ),
    )
    monkeypatch.setattr(
        queue_monitoring_service_module,
        "list_worker_heartbeats",
        lambda _db, *, worker_type: [
            WorkerHeartbeatRead(
                worker_type=worker_type,
                worker_id=f"{worker_type}_1",
                last_seen_at=generated_at,
                active=True,
                pending_tasks=1,
            )
        ]
        if worker_type == "rss_scrapper"
        else [],
    )
    monkeypatch.setattr(
        queue_monitoring_service_module,
        "_list_stuck_task_leases",
        lambda _db, *, task_kind, stuck_pending_threshold_ms: [],
    )

    class _FakeDatetime:
        @staticmethod
        def now(tz=None):
            return generated_at

    monkeypatch.setattr(queue_monitoring_service_module, "datetime", _FakeDatetime)

    result = queue_monitoring_service_module.get_queues_overview(db)

    assert result.queue_backend_available is True
    assert result.blocked_queues == 0
    assert result.items[0].queue_name == "rss_scrape_requests"
    assert result.items[0].queue_length == 4


def test_purge_task_queue_validates_local_payload(monkeypatch) -> None:
    db = Mock(spec=Session)
    purged_at = datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        queue_monitoring_service_module,
        "purge_task_queue_rows",
        lambda _db, *, task_kind: 3 if task_kind == "rss_scrape" else 0,
    )

    class _FakeDatetime:
        @staticmethod
        def now(tz=None):
            return purged_at

    monkeypatch.setattr(queue_monitoring_service_module, "datetime", _FakeDatetime)

    result = queue_monitoring_service_module.purge_task_queue(db, "rss_scrape_requests")

    assert result.queue_name == "rss_scrape_requests"
    assert result.deleted is True
    db.commit.assert_called_once()
