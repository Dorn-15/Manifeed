from datetime import datetime, timezone
from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.services.internal.worker_monitoring_service as worker_monitoring_service_module
from app.clients.database.worker_queue_db_client import TaskQueueState, WorkerHeartbeatRead


def test_get_workers_overview_validates_local_payload(monkeypatch) -> None:
    db = Mock(spec=Session)
    generated_at = datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        worker_monitoring_service_module,
        "_resolve_threshold_ms",
        lambda env_name, default_value: default_value,
    )
    monkeypatch.setattr(
        worker_monitoring_service_module,
        "get_task_queue_state",
        lambda _db, *, task_kind: TaskQueueState(
            pending=3 if task_kind == "source_embedding" else 0,
            processing=1 if task_kind == "source_embedding" else 0,
            completed=0,
            failed=0,
            total=4 if task_kind == "source_embedding" else 0,
            last_task_id=12 if task_kind == "source_embedding" else None,
        ),
    )
    monkeypatch.setattr(
        worker_monitoring_service_module,
        "list_worker_heartbeats",
        lambda _db, *, worker_type: [
            WorkerHeartbeatRead(
                worker_type=worker_type,
                worker_id="device-embedding-1",
                last_seen_at=generated_at,
                active=True,
                pending_tasks=1,
                connection_state="connected",
                desired_state="running",
                current_task_id=12,
                current_execution_id=44,
                current_task_label="embedding task 12",
            )
        ]
        if worker_type == "source_embedding"
        else [],
    )

    class _FakeDatetime:
        @staticmethod
        def now(tz=None):
            return generated_at

    monkeypatch.setattr(worker_monitoring_service_module, "datetime", _FakeDatetime)

    result = worker_monitoring_service_module.get_workers_overview(db)

    assert result.items[1].worker_type == "source_embedding"
    assert result.items[1].queue_length == 4
    assert result.items[1].workers[0].current_task_id == 12
    assert result.items[1].workers[0].current_task_label == "embedding task 12"
