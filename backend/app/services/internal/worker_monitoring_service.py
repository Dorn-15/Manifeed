from __future__ import annotations

from datetime import datetime, timezone
import os

from sqlalchemy.orm import Session

from app.clients.database import (
    QUEUE_NAME_RSS_SCRAPE_REQUESTS,
    QUEUE_NAME_SOURCE_EMBEDDING_REQUESTS,
    TASK_KIND_RSS_SCRAPE,
    TASK_KIND_SOURCE_EMBEDDING,
    WORKER_TYPE_RSS_SCRAPPER,
    WORKER_TYPE_SOURCE_EMBEDDING,
    get_task_queue_state,
    list_worker_heartbeats,
)
from app.schemas.internal import WorkerOverviewRead
from app.schemas.internal.worker_overview_schema import WorkerInstanceRead, WorkerTypeOverviewRead

DEFAULT_CONNECTED_IDLE_THRESHOLD_MS = 5 * 60 * 1000
DEFAULT_ACTIVE_IDLE_THRESHOLD_MS = 30 * 1000


def get_workers_overview(db: Session) -> WorkerOverviewRead:
    connected_threshold_ms = _resolve_threshold_ms(
        "WORKER_CONNECTED_IDLE_THRESHOLD_MS",
        DEFAULT_CONNECTED_IDLE_THRESHOLD_MS,
    )
    active_threshold_ms = min(
        connected_threshold_ms,
        _resolve_threshold_ms("WORKER_ACTIVE_IDLE_THRESHOLD_MS", DEFAULT_ACTIVE_IDLE_THRESHOLD_MS),
    )
    generated_at = datetime.now(timezone.utc)

    return WorkerOverviewRead(
        generated_at=generated_at,
        connected_idle_threshold_ms=connected_threshold_ms,
        active_idle_threshold_ms=active_threshold_ms,
        items=[
            _build_worker_type_overview(
                db,
                generated_at=generated_at,
                connected_threshold_ms=connected_threshold_ms,
                active_threshold_ms=active_threshold_ms,
                worker_type=WORKER_TYPE_RSS_SCRAPPER,
                queue_name=QUEUE_NAME_RSS_SCRAPE_REQUESTS,
                task_kind=TASK_KIND_RSS_SCRAPE,
            ),
            _build_worker_type_overview(
                db,
                generated_at=generated_at,
                connected_threshold_ms=connected_threshold_ms,
                active_threshold_ms=active_threshold_ms,
                worker_type=WORKER_TYPE_SOURCE_EMBEDDING,
                queue_name=QUEUE_NAME_SOURCE_EMBEDDING_REQUESTS,
                task_kind=TASK_KIND_SOURCE_EMBEDDING,
            ),
        ],
    )


def _build_worker_type_overview(
    db: Session,
    *,
    generated_at: datetime,
    connected_threshold_ms: int,
    active_threshold_ms: int,
    worker_type: str,
    queue_name: str,
    task_kind: str,
) -> WorkerTypeOverviewRead:
    queue_state = get_task_queue_state(db, task_kind=task_kind)
    workers = _build_worker_instance_reads(
        list_worker_heartbeats(db, worker_type=worker_type),
        generated_at=generated_at,
        connected_threshold_ms=connected_threshold_ms,
        active_threshold_ms=active_threshold_ms,
    )

    return WorkerTypeOverviewRead(
        worker_type=worker_type,
        queue_name=queue_name,
        queue_length=queue_state.pending + queue_state.processing,
        queued_tasks=queue_state.pending,
        processing_tasks=queue_state.processing,
        worker_count=len(workers),
        connected=any(worker.connected for worker in workers),
        active=any(worker.active for worker in workers),
        workers=workers,
    )


def _build_worker_instance_reads(
    heartbeats,
    *,
    generated_at: datetime,
    connected_threshold_ms: int,
    active_threshold_ms: int,
) -> list[WorkerInstanceRead]:
    workers: list[WorkerInstanceRead] = []
    for heartbeat in heartbeats:
        idle_ms = max(0, int((generated_at - heartbeat.last_seen_at).total_seconds() * 1000))
        connected = idle_ms <= connected_threshold_ms
        active = connected and idle_ms <= active_threshold_ms
        workers.append(
            WorkerInstanceRead(
                name=heartbeat.worker_id,
                processing_tasks=heartbeat.pending_tasks,
                idle_ms=idle_ms,
                connected=connected,
                active=active,
                connection_state=heartbeat.connection_state,
                desired_state=heartbeat.desired_state,
                current_task_id=heartbeat.current_task_id,
                current_execution_id=heartbeat.current_execution_id,
                current_task_label=heartbeat.current_task_label,
                current_feed_id=heartbeat.current_feed_id,
                current_feed_url=heartbeat.current_feed_url,
                last_error=heartbeat.last_error,
            )
        )
    workers.sort(key=lambda worker: worker.name)
    return workers


def _resolve_threshold_ms(env_name: str, default_value: int) -> int:
    raw_value = os.getenv(env_name, str(default_value)).strip()
    try:
        parsed = int(raw_value)
    except ValueError:
        return default_value
    if parsed <= 0:
        return default_value
    return parsed
