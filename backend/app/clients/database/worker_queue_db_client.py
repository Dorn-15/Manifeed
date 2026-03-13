from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from typing import TypeVar
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.rss import RssScrapeFeedPayloadSchema
from app.schemas.sources import RssSourceEmbeddingPayloadSchema

TASK_KIND_RSS_SCRAPE = "rss_scrape"
TASK_KIND_SOURCE_EMBEDDING = "source_embedding"

WORKER_TYPE_RSS_SCRAPPER = "rss_scrapper"
WORKER_TYPE_SOURCE_EMBEDDING = "source_embedding"

QUEUE_NAME_RSS_SCRAPE_REQUESTS = "rss_scrape_requests"
QUEUE_NAME_SOURCE_EMBEDDING_REQUESTS = "rss_source_embedding_requests"

DEFAULT_RSS_TASK_BATCH_SIZE = 20
DEFAULT_SOURCE_EMBEDDING_TASK_BATCH_SIZE = 128
_T = TypeVar("_T")


@dataclass(frozen=True)
class TaskQueueState:
    pending: int
    processing: int
    completed: int
    failed: int
    total: int
    last_task_id: int | None


@dataclass(frozen=True)
class WorkerHeartbeatRead:
    worker_type: str
    worker_id: str
    last_seen_at: datetime
    active: bool
    pending_tasks: int
    connection_state: str | None = None
    desired_state: str | None = None
    current_task_id: int | None = None
    current_execution_id: int | None = None
    current_task_label: str | None = None
    current_feed_id: int | None = None
    current_feed_url: str | None = None
    last_error: str | None = None


def get_worker_instance_id(
    db: Session,
    *,
    worker_type: str,
    worker_name: str,
) -> int | None:
    row = (
        db.execute(
            text(
                """
                SELECT id
                FROM worker_instances
                WHERE worker_kind = :worker_kind
                    AND worker_name = :worker_name
                """
            ),
            {
                "worker_kind": worker_type,
                "worker_name": worker_name,
            },
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return int(row["id"])


def enqueue_rss_scrape_tasks(
    db: Session,
    *,
    job_id: str,
    requested_at: datetime,
    feed_batches: list[list[RssScrapeFeedPayloadSchema]],
) -> int:
    if not feed_batches:
        return 0

    created_at = _normalize_datetime(requested_at)
    task_count = 0
    for batch_no, batch in enumerate(feed_batches, start=1):
        task_id = db.execute(
            text(
                """
                INSERT INTO rss_scrape_tasks (
                    job_id,
                    batch_no,
                    status,
                    attempt_count,
                    feeds_total,
                    feeds_processed,
                    feeds_success,
                    feeds_error,
                    created_at,
                    updated_at
                ) VALUES (
                    :job_id,
                    :batch_no,
                    'pending',
                    0,
                    :feeds_total,
                    0,
                    0,
                    0,
                    :created_at,
                    :created_at
                )
                RETURNING id
                """
            ),
            {
                "job_id": job_id,
                "batch_no": batch_no,
                "feeds_total": len(batch),
                "created_at": created_at,
            },
        ).scalar_one()
        db.execute(
            text(
                """
                INSERT INTO rss_scrape_task_items (
                    task_id,
                    feed_id,
                    item_no,
                    requested_cursor_published_at,
                    status,
                    sources_count
                ) VALUES (
                    :task_id,
                    :feed_id,
                    :item_no,
                    :requested_cursor_published_at,
                    'pending',
                    0
                )
                """
            ),
            [
                {
                    "task_id": task_id,
                    "feed_id": feed.feed_id,
                    "item_no": item_no,
                    "requested_cursor_published_at": feed.last_db_article_published_at,
                }
                for item_no, feed in enumerate(batch, start=1)
            ],
        )
        task_count += 1
    return task_count


def create_source_embedding_job(
    db: Session,
    *,
    requested_by: str,
    requested_at: datetime,
    initial_status: str,
    tasks_total: int,
    items_total: int,
) -> str:
    job_id = f"embedding-{uuid4()}"
    db.execute(
        text(
            """
            INSERT INTO worker_jobs (
                id,
                job_kind,
                requested_by,
                status,
                requested_at,
                tasks_total,
                tasks_processed,
                items_total,
                items_processed,
                items_success,
                items_error,
                created_at,
                updated_at
            ) VALUES (
                :job_id,
                'source_embedding',
                :requested_by,
                :status,
                :requested_at,
                :tasks_total,
                0,
                :items_total,
                0,
                0,
                0,
                :requested_at,
                :requested_at
            )
            """
        ),
        {
            "job_id": job_id,
            "requested_by": requested_by,
            "status": initial_status,
            "requested_at": _normalize_datetime(requested_at),
            "tasks_total": max(0, int(tasks_total)),
            "items_total": max(0, int(items_total)),
        },
    )
    return job_id


def enqueue_source_embedding_tasks(
    db: Session,
    *,
    job_id: str,
    model_name: str,
    requested_at: datetime,
    sources: list[RssSourceEmbeddingPayloadSchema],
) -> int:
    if not sources:
        return 0

    created_at = _normalize_datetime(requested_at)
    embedding_model_id = _get_or_create_embedding_model_id(db, model_name=model_name)
    task_count = 0
    batch_size = resolve_source_embedding_task_batch_size()
    for batch_no, batch in enumerate(_chunked(sources, batch_size), start=1):
        task_id = db.execute(
            text(
                """
                INSERT INTO source_embedding_tasks (
                    job_id,
                    embedding_model_id,
                    batch_no,
                    status,
                    attempt_count,
                    sources_total,
                    sources_processed,
                    sources_success,
                    sources_error,
                    created_at,
                    updated_at
                ) VALUES (
                    :job_id,
                    :embedding_model_id,
                    :batch_no,
                    'pending',
                    0,
                    :sources_total,
                    0,
                    0,
                    0,
                    :created_at,
                    :created_at
                )
                RETURNING id
                """
            ),
            {
                "job_id": job_id,
                "embedding_model_id": embedding_model_id,
                "batch_no": batch_no,
                "sources_total": len(batch),
                "created_at": created_at,
            },
        ).scalar_one()
        db.execute(
            text(
                """
                INSERT INTO source_embedding_task_items (
                    task_id,
                    source_id,
                    item_no,
                    status
                ) VALUES (
                    :task_id,
                    :source_id,
                    :item_no,
                    'pending'
                )
                """
            ),
            [
                {
                    "task_id": task_id,
                    "source_id": source.id,
                    "item_no": item_no,
                }
                for item_no, source in enumerate(batch, start=1)
            ],
        )
        task_count += 1
    return task_count


def get_task_queue_state(
    db: Session,
    *,
    task_kind: str,
) -> TaskQueueState:
    task_table = _resolve_task_table(task_kind)
    row = db.execute(
        text(
            f"""
            SELECT
                COUNT(*) FILTER (WHERE task.status = 'pending') AS pending_count,
                COUNT(*) FILTER (WHERE task.status = 'processing') AS processing_count,
                COUNT(*) FILTER (WHERE task.status = 'completed') AS completed_count,
                COUNT(*) FILTER (WHERE task.status = 'failed') AS failed_count,
                COUNT(*) AS total_count,
                MAX(task.id) AS last_task_id
            FROM {task_table} AS task
            """
        )
    ).mappings().one()

    return TaskQueueState(
        pending=int(row["pending_count"] or 0),
        processing=int(row["processing_count"] or 0),
        completed=int(row["completed_count"] or 0),
        failed=int(row["failed_count"] or 0),
        total=int(row["total_count"] or 0),
        last_task_id=(int(row["last_task_id"]) if row["last_task_id"] is not None else None),
    )


def purge_task_queue(
    db: Session,
    *,
    task_kind: str,
) -> int:
    task_table = _resolve_task_table(task_kind)
    deleted = db.execute(
        text(
            f"""
            WITH deleted_tasks AS (
                DELETE FROM {task_table}
                RETURNING id
            )
            SELECT COUNT(*) FROM deleted_tasks
            """
        )
    ).scalar_one()
    return int(deleted or 0)


def list_worker_heartbeats(
    db: Session,
    *,
    worker_type: str,
) -> list[WorkerHeartbeatRead]:
    rows = (
        db.execute(
            text(
                """
                SELECT
                    worker_kind,
                    worker_name,
                    last_seen_at,
                    active,
                    pending_tasks,
                    connection_state,
                    desired_state,
                    current_task_id,
                    current_execution_id,
                    current_task_label,
                    current_feed_id,
                    current_feed_url,
                    last_error
                FROM worker_instances
                WHERE worker_kind = :worker_type
                ORDER BY worker_name ASC
                """
            ),
            {"worker_type": worker_type},
        )
        .mappings()
        .all()
    )

    return [
        WorkerHeartbeatRead(
            worker_type=str(row["worker_kind"]),
            worker_id=str(row["worker_name"]),
            last_seen_at=_normalize_datetime(row["last_seen_at"]) or datetime.now(timezone.utc),
            active=bool(row["active"]),
            pending_tasks=int(row["pending_tasks"] or 0),
            connection_state=(
                str(row["connection_state"]) if row["connection_state"] is not None else None
            ),
            desired_state=(str(row["desired_state"]) if row["desired_state"] is not None else None),
            current_task_id=(
                int(row["current_task_id"]) if row["current_task_id"] is not None else None
            ),
            current_execution_id=(
                int(row["current_execution_id"]) if row["current_execution_id"] is not None else None
            ),
            current_task_label=(
                str(row["current_task_label"]) if row["current_task_label"] is not None else None
            ),
            current_feed_id=(
                int(row["current_feed_id"]) if row["current_feed_id"] is not None else None
            ),
            current_feed_url=(
                str(row["current_feed_url"]) if row["current_feed_url"] is not None else None
            ),
            last_error=(str(row["last_error"]) if row["last_error"] is not None else None),
        )
        for row in rows
    ]


def upsert_worker_instance_state(
    db: Session,
    *,
    identity_id: int | None,
    worker_type: str,
    worker_name: str,
    active: bool,
    pending_tasks: int,
    connection_state: str | None,
    desired_state: str | None,
    current_task_id: int | None,
    current_execution_id: int | None,
    current_task_label: str | None,
    current_feed_id: int | None,
    current_feed_url: str | None,
    last_error: str | None,
) -> int:
    row = (
        db.execute(
            text(
                """
                INSERT INTO worker_instances (
                    identity_id,
                    worker_kind,
                    worker_name,
                    last_seen_at,
                    active,
                    pending_tasks,
                    connection_state,
                    current_task_id,
                    current_execution_id,
                    current_task_label,
                    current_feed_id,
                    current_feed_url,
                    last_error,
                    last_heartbeat_at,
                    desired_state,
                    created_at,
                    updated_at
                ) VALUES (
                    :identity_id,
                    :worker_kind,
                    :worker_name,
                    now(),
                    :active,
                    :pending_tasks,
                    :connection_state,
                    :current_task_id,
                    :current_execution_id,
                    :current_task_label,
                    :current_feed_id,
                    :current_feed_url,
                    :last_error,
                    now(),
                    :desired_state,
                    now(),
                    now()
                )
                ON CONFLICT (worker_kind, worker_name)
                DO UPDATE SET
                    identity_id = EXCLUDED.identity_id,
                    last_seen_at = EXCLUDED.last_seen_at,
                    active = EXCLUDED.active,
                    pending_tasks = EXCLUDED.pending_tasks,
                    connection_state = EXCLUDED.connection_state,
                    current_task_id = EXCLUDED.current_task_id,
                    current_execution_id = EXCLUDED.current_execution_id,
                    current_task_label = EXCLUDED.current_task_label,
                    current_feed_id = EXCLUDED.current_feed_id,
                    current_feed_url = EXCLUDED.current_feed_url,
                    last_error = EXCLUDED.last_error,
                    last_heartbeat_at = EXCLUDED.last_heartbeat_at,
                    desired_state = EXCLUDED.desired_state,
                    updated_at = EXCLUDED.updated_at
                RETURNING id
                """
            ),
            {
                "identity_id": (int(identity_id) if identity_id is not None else None),
                "worker_kind": worker_type,
                "worker_name": worker_name,
                "active": bool(active),
                "pending_tasks": max(0, int(pending_tasks)),
                "connection_state": connection_state,
                "current_task_id": current_task_id,
                "current_execution_id": current_execution_id,
                "current_task_label": current_task_label,
                "current_feed_id": current_feed_id,
                "current_feed_url": current_feed_url,
                "last_error": last_error,
                "desired_state": desired_state,
            },
        )
        .mappings()
        .one()
    )
    return int(row["id"])


def _get_or_create_embedding_model_id(db: Session, *, model_name: str) -> int:
    row = db.execute(
        text(
            """
            INSERT INTO embedding_models (
                code,
                label,
                active,
                created_at,
                updated_at
            ) VALUES (
                :model_name,
                :model_name,
                TRUE,
                now(),
                now()
            )
            ON CONFLICT (code) DO UPDATE
            SET updated_at = now()
            RETURNING id
            """
        ),
        {"model_name": model_name},
    ).mappings().one()
    return int(row["id"])


def _resolve_task_table(task_kind: str) -> str:
    if task_kind == TASK_KIND_RSS_SCRAPE:
        return "rss_scrape_tasks"
    if task_kind == TASK_KIND_SOURCE_EMBEDDING:
        return "source_embedding_tasks"
    raise ValueError(f"Unsupported task kind: {task_kind}")


def resolve_rss_scrape_task_batch_size() -> int:
    return min(
        20,
        _resolve_batch_size(
        env_name="RSS_SCRAPE_TASK_BATCH_SIZE",
        default_value=DEFAULT_RSS_TASK_BATCH_SIZE,
        ),
    )


def resolve_source_embedding_task_batch_size() -> int:
    return _resolve_batch_size(
        env_name="SOURCE_EMBEDDING_TASK_BATCH_SIZE",
        default_value=DEFAULT_SOURCE_EMBEDDING_TASK_BATCH_SIZE,
    )


def _resolve_batch_size(*, env_name: str, default_value: int) -> int:
    raw_value = os.getenv(env_name, str(default_value)).strip()
    try:
        parsed = int(raw_value)
    except ValueError:
        return default_value
    if parsed <= 0:
        return default_value
    return parsed


def _chunked(items: list[_T], batch_size: int) -> Iterable[list[_T]]:
    normalized_batch_size = max(1, batch_size)
    for start in range(0, len(items), normalized_batch_size):
        yield items[start : start + normalized_batch_size]


def _normalize_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
