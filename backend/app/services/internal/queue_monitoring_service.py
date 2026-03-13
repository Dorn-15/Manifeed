from __future__ import annotations

from datetime import datetime, timezone
import os

from fastapi import HTTPException
from sqlalchemy import text
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
    purge_task_queue as purge_task_queue_rows,
)
from app.schemas.internal import QueueOverviewRead, QueuePurgeRead
from app.schemas.internal.queue_overview_schema import (
    QueueWorkerRead,
    TaskLeaseRead,
    TaskQueueOverviewRead,
)

DEFAULT_CONNECTED_IDLE_THRESHOLD_MS = 5 * 60 * 1000
DEFAULT_ACTIVE_IDLE_THRESHOLD_MS = 30 * 1000
DEFAULT_STUCK_PENDING_THRESHOLD_MS = 2 * 60 * 1000


def get_queues_overview(db: Session) -> QueueOverviewRead:
    connected_threshold_ms = _resolve_threshold_ms(
        "QUEUE_CONNECTED_IDLE_THRESHOLD_MS",
        DEFAULT_CONNECTED_IDLE_THRESHOLD_MS,
    )
    active_threshold_ms = min(
        connected_threshold_ms,
        _resolve_threshold_ms("QUEUE_ACTIVE_IDLE_THRESHOLD_MS", DEFAULT_ACTIVE_IDLE_THRESHOLD_MS),
    )
    stuck_pending_threshold_ms = _resolve_threshold_ms(
        "QUEUE_STUCK_PENDING_THRESHOLD_MS",
        DEFAULT_STUCK_PENDING_THRESHOLD_MS,
    )
    generated_at = datetime.now(timezone.utc)
    items = [
        _build_task_queue_overview(
            db,
            queue_name=QUEUE_NAME_RSS_SCRAPE_REQUESTS,
            purpose="RSS scrape tasks produced by backend and claimed by RSS worker",
            worker_type=WORKER_TYPE_RSS_SCRAPPER,
            task_kind=TASK_KIND_RSS_SCRAPE,
            generated_at=generated_at,
            connected_threshold_ms=connected_threshold_ms,
            active_threshold_ms=active_threshold_ms,
            stuck_pending_threshold_ms=stuck_pending_threshold_ms,
        ),
        _build_task_queue_overview(
            db,
            queue_name=QUEUE_NAME_SOURCE_EMBEDDING_REQUESTS,
            purpose="Source embedding tasks produced by backend and claimed by embedding worker",
            worker_type=WORKER_TYPE_SOURCE_EMBEDDING,
            task_kind=TASK_KIND_SOURCE_EMBEDDING,
            generated_at=generated_at,
            connected_threshold_ms=connected_threshold_ms,
            active_threshold_ms=active_threshold_ms,
            stuck_pending_threshold_ms=stuck_pending_threshold_ms,
        ),
    ]
    return QueueOverviewRead(
        generated_at=generated_at,
        connected_idle_threshold_ms=connected_threshold_ms,
        active_idle_threshold_ms=active_threshold_ms,
        stuck_pending_threshold_ms=stuck_pending_threshold_ms,
        queue_backend_available=True,
        queue_backend_error=None,
        blocked_queues=sum(1 for item in items if item.blocked),
        items=items,
    )


def purge_task_queue(db: Session, queue_name: str) -> QueuePurgeRead:
    task_kind = _resolve_task_kind(queue_name)
    deleted = purge_task_queue_rows(db, task_kind=task_kind)
    db.commit()
    return QueuePurgeRead(
        queue_name=queue_name,
        deleted=bool(deleted),
        purged_at=datetime.now(timezone.utc),
    )


def _build_task_queue_overview(
    db: Session,
    *,
    queue_name: str,
    purpose: str,
    worker_type: str,
    task_kind: str,
    generated_at: datetime,
    connected_threshold_ms: int,
    active_threshold_ms: int,
    stuck_pending_threshold_ms: int,
) -> TaskQueueOverviewRead:
    queue_state = get_task_queue_state(db, task_kind=task_kind)
    workers = _build_queue_worker_reads(
        list_worker_heartbeats(db, worker_type=worker_type),
        generated_at=generated_at,
        connected_threshold_ms=connected_threshold_ms,
        active_threshold_ms=active_threshold_ms,
    )
    leased_tasks = _list_stuck_task_leases(
        db,
        task_kind=task_kind,
        stuck_pending_threshold_ms=stuck_pending_threshold_ms,
    )
    connected_workers = sum(1 for worker in workers if worker.connected)
    active_workers = sum(1 for worker in workers if worker.active)
    blocked_reasons: list[str] = []
    if queue_state.pending + queue_state.processing > 0 and connected_workers == 0:
        blocked_reasons.append("Queue has tasks but no connected worker")
    if queue_state.processing > 0 and active_workers == 0:
        blocked_reasons.append("Processing tasks but no active worker")
    if leased_tasks:
        blocked_reasons.append("Stuck leased tasks detected")

    return TaskQueueOverviewRead(
        queue_name=queue_name,
        purpose=purpose,
        worker_type=worker_type,
        queue_exists=queue_state.total > 0,
        queue_length=queue_state.pending + queue_state.processing,
        queued_tasks=queue_state.pending,
        processing_tasks=queue_state.processing,
        last_task_id=(str(queue_state.last_task_id) if queue_state.last_task_id is not None else None),
        connected_workers=connected_workers,
        active_workers=active_workers,
        blocked=bool(blocked_reasons),
        blocked_reasons=blocked_reasons,
        workers=workers,
        leased_tasks=leased_tasks,
    )


def _build_queue_worker_reads(
    heartbeats,
    *,
    generated_at: datetime,
    connected_threshold_ms: int,
    active_threshold_ms: int,
) -> list[QueueWorkerRead]:
    workers: list[QueueWorkerRead] = []
    for heartbeat in heartbeats:
        idle_ms = max(0, int((generated_at - heartbeat.last_seen_at).total_seconds() * 1000))
        connected = idle_ms <= connected_threshold_ms
        active = connected and idle_ms <= active_threshold_ms
        workers.append(
            QueueWorkerRead(
                name=heartbeat.worker_id,
                processing_tasks=heartbeat.pending_tasks,
                idle_ms=idle_ms,
                connected=connected,
                active=active,
            )
        )
    workers.sort(key=lambda worker: worker.name)
    return workers


def _list_stuck_task_leases(
    db: Session,
    *,
    task_kind: str,
    stuck_pending_threshold_ms: int,
) -> list[TaskLeaseRead]:
    task_table, execution_table = _resolve_processing_tables(task_kind)
    rows = (
        db.execute(
            text(
                f"""
                SELECT
                    task.id AS task_id,
                    instance.worker_name AS worker_name,
                    CASE
                        WHEN execution.started_at IS NOT NULL
                            THEN GREATEST(
                                0,
                                FLOOR(EXTRACT(EPOCH FROM (now() - execution.started_at)) * 1000)
                            )::BIGINT
                        ELSE 0
                    END AS idle_ms,
                    COALESCE(task.attempt_count, 0) AS attempts
                FROM {task_table} AS task
                LEFT JOIN LATERAL (
                    SELECT exec.worker_instance_id, exec.started_at
                    FROM (
                        SELECT
                            id,
                            worker_instance_id,
                            started_at,
                            ROW_NUMBER() OVER (
                                PARTITION BY task_id
                                ORDER BY started_at DESC NULLS LAST, id DESC
                            ) AS rank_no
                        FROM {execution_table}
                        WHERE task_id = task.id
                    ) AS exec
                    WHERE exec.rank_no = 1
                ) AS execution
                    ON TRUE
                LEFT JOIN worker_instances AS instance
                    ON instance.id = execution.worker_instance_id
                WHERE task.status = 'processing'
                ORDER BY task.id ASC
                """
            )
        )
        .mappings()
        .all()
    )
    stuck_leases: list[TaskLeaseRead] = []
    for row in rows:
        idle_ms = max(0, int(row["idle_ms"] or 0))
        if idle_ms < stuck_pending_threshold_ms:
            continue
        stuck_leases.append(
            TaskLeaseRead(
                task_id=str(row["task_id"]),
                worker_name=(str(row["worker_name"]) if row["worker_name"] is not None else None),
                idle_ms=idle_ms,
                attempts=max(0, int(row["attempts"] or 0)),
            )
        )
    return stuck_leases


def _resolve_task_kind(queue_name: str) -> str:
    if queue_name == QUEUE_NAME_RSS_SCRAPE_REQUESTS:
        return TASK_KIND_RSS_SCRAPE
    if queue_name == QUEUE_NAME_SOURCE_EMBEDDING_REQUESTS:
        return TASK_KIND_SOURCE_EMBEDDING
    raise HTTPException(status_code=404, detail=f"Unknown task queue '{queue_name}'")


def _resolve_processing_tables(task_kind: str) -> tuple[str, str]:
    if task_kind == TASK_KIND_RSS_SCRAPE:
        return "rss_scrape_tasks", "rss_scrape_task_executions"
    if task_kind == TASK_KIND_SOURCE_EMBEDDING:
        return "source_embedding_tasks", "source_embedding_task_executions"
    raise ValueError(f"Unsupported task kind: {task_kind}")


def _resolve_threshold_ms(env_name: str, default_value: int) -> int:
    raw_value = os.getenv(env_name, str(default_value)).strip()
    try:
        parsed = int(raw_value)
    except ValueError:
        return default_value
    if parsed <= 0:
        return default_value
    return parsed
