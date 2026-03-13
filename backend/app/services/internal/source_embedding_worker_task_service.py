from __future__ import annotations
from typing import Any
from sqlalchemy import text

from app.clients.database import upsert_source_embeddings, upsert_worker_instance_state
from database import open_db_session
from app.schemas import WorkerEmbeddingResultPayloadSchema, WorkerEmbeddingResultSchema

WORKER_TYPE_SOURCE_EMBEDDING = "source_embedding"


def claim_embedding_tasks(
    *,
    worker_identity_id: int,
    worker_id: str,
    count: int,
    lease_seconds: int,
) -> list[tuple[int, int, dict[str, Any]]]:
    db = open_db_session()
    try:
        worker_instance_id = upsert_worker_instance_state(
            db,
            identity_id=worker_identity_id,
            worker_type=WORKER_TYPE_SOURCE_EMBEDDING,
            worker_name=worker_id,
            active=True,
            pending_tasks=max(0, count),
            connection_state="connected",
            desired_state="running",
            current_task_id=None,
            current_execution_id=None,
            current_task_label=None,
            current_feed_id=None,
            current_feed_url=None,
            last_error=None,
        )
        rows = db.execute(
            text(
                """
                WITH candidate AS (
                    SELECT task.id
                    FROM source_embedding_tasks AS task
                    WHERE task.status = 'pending'
                        OR (
                            task.status = 'processing'
                            AND task.claim_expires_at IS NOT NULL
                            AND task.claim_expires_at < now()
                        )
                    ORDER BY task.id ASC
                    LIMIT :task_count
                    FOR UPDATE SKIP LOCKED
                ),
                claimed AS (
                    UPDATE source_embedding_tasks AS task
                    SET
                        status = CAST('processing' AS worker_task_status_enum),
                        last_claimed_at = now(),
                        claim_expires_at = now() + (:lease_seconds * interval '1 second'),
                        attempt_count = task.attempt_count + 1,
                        updated_at = now()
                    FROM candidate
                    WHERE task.id = candidate.id
                    RETURNING
                        task.id,
                        task.attempt_count,
                        task.job_id
                ),
                executions AS (
                    INSERT INTO source_embedding_task_executions (
                        task_id,
                        worker_instance_id,
                        attempt_no,
                        started_at,
                        created_at
                    )
                    SELECT
                        claimed.id,
                        :worker_instance_id,
                        claimed.attempt_count,
                        now(),
                        now()
                    FROM claimed
                    RETURNING
                        id,
                        task_id
                )
                SELECT
                    task.id AS task_id,
                    executions.id AS execution_id,
                    task.job_id,
                    item.source_id,
                    item.item_no,
                    content.title,
                    content.summary,
                    source.url
                FROM executions
                JOIN source_embedding_tasks AS task
                    ON task.id = executions.task_id
                JOIN source_embedding_task_items AS item
                    ON item.task_id = task.id
                JOIN rss_sources AS source
                    ON source.id = item.source_id
                JOIN rss_source_contents AS content
                    ON content.source_id = source.id
                    AND content.ingested_at = source.ingested_at
                ORDER BY task.id ASC, item.item_no ASC
                """
            ),
            {
                "task_count": max(1, count),
                "lease_seconds": max(30, lease_seconds),
                "worker_instance_id": worker_instance_id,
            },
        ).mappings().all()

        job_ids = sorted({str(row["job_id"]) for row in rows})
        if job_ids:
            db.execute(
                text(
                    """
                    UPDATE worker_jobs
                    SET
                        status = CAST('processing' AS worker_job_status_enum),
                        started_at = COALESCE(started_at, now()),
                        updated_at = now()
                    WHERE id = ANY(:job_ids)
                    """
                ),
                {"job_ids": job_ids},
            )
        db.commit()
    except Exception as exception:
        db.rollback()
        raise RuntimeError(f"Unable to claim embedding tasks: {exception}") from exception
    finally:
        db.close()

    claimed_tasks: list[tuple[int, int, dict[str, Any]]] = []
    current_task_id: int | None = None
    current_execution_id: int | None = None
    current_payload: dict[str, Any] | None = None

    for row in rows:
        task_id = int(row["task_id"])
        execution_id = int(row["execution_id"])
        if current_task_id != task_id:
            if current_task_id is not None and current_execution_id is not None and current_payload is not None:
                claimed_tasks.append((current_task_id, current_execution_id, current_payload))
            current_task_id = task_id
            current_execution_id = execution_id
            current_payload = {
                "job_id": str(row["job_id"]),
                "sources": [],
            }

        assert current_payload is not None
        current_payload["sources"].append(
            {
                "id": int(row["source_id"]),
                "title": str(row["title"]),
                "summary": (str(row["summary"]) if row["summary"] is not None else None),
                "url": str(row["url"]),
            }
        )

    if current_task_id is not None and current_execution_id is not None and current_payload is not None:
        claimed_tasks.append((current_task_id, current_execution_id, current_payload))

    if claimed_tasks:
        db = open_db_session()
        try:
            first_task_id, first_execution_id, first_payload = claimed_tasks[0]
            upsert_worker_instance_state(
                db,
                identity_id=worker_identity_id,
                worker_type=WORKER_TYPE_SOURCE_EMBEDDING,
                worker_name=worker_id,
                active=True,
                pending_tasks=len(claimed_tasks),
                connection_state="connected",
                desired_state="running",
                current_task_id=first_task_id,
                current_execution_id=first_execution_id,
                current_task_label=f"embedding task {first_task_id}",
                current_feed_id=None,
                current_feed_url=None,
                last_error=None,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    return claimed_tasks


def complete_embedding_task(
    *,
    worker_identity_id: int,
    worker_id: str,
    task_id: int,
    execution_id: int,
    result_payload: dict[str, Any],
) -> None:
    db = open_db_session()
    try:
        current_worker_instance_id = upsert_worker_instance_state(
            db,
            identity_id=worker_identity_id,
            worker_type=WORKER_TYPE_SOURCE_EMBEDDING,
            worker_name=worker_id,
            active=True,
            pending_tasks=0,
            connection_state="connected",
            desired_state="running",
            current_task_id=None,
            current_execution_id=None,
            current_task_label=None,
            current_feed_id=None,
            current_feed_url=None,
            last_error=None,
        )
        row = _get_execution_row(db, task_id=task_id, execution_id=execution_id)
        if current_worker_instance_id != int(row["worker_instance_id"]):
            raise RuntimeError(
                f"Embedding task {task_id} execution {execution_id} is not owned by worker {worker_id}"
            )

        result_sources = WorkerEmbeddingResultPayloadSchema.model_validate(result_payload)
        expected_source_ids = _list_task_source_ids(db, task_id=task_id)
        seen_source_ids = {int(source.id) for source in result_sources.sources}
        if seen_source_ids != expected_source_ids:
            raise RuntimeError(
                f"Embedding task {task_id} completed sources {sorted(seen_source_ids)} "
                f"but expected {sorted(expected_source_ids)}"
            )

        upsert_source_embeddings(
            db,
            payload=WorkerEmbeddingResultSchema(
                model_name=str(row["model_name"]),
                sources=list(result_sources.sources),
            ),
        )
        embedding_dimensions = len(result_sources.sources[0].embedding) if result_sources.sources else 0

        db.execute(
            text(
                """
                UPDATE source_embedding_task_items
                SET
                    status = 'success',
                    error_message = NULL,
                    embedding_dimensions = :embedding_dimensions,
                    completed_at = now()
                WHERE task_id = :task_id
                    AND source_id = ANY(:source_ids)
                """
            ),
            {
                "task_id": task_id,
                "source_ids": sorted(seen_source_ids),
                "embedding_dimensions": embedding_dimensions,
            },
        )

        task_summary = _refresh_embedding_task_summary(db, task_id=task_id, terminal_status="completed")
        db.execute(
            text(
                """
                UPDATE source_embedding_task_executions
                SET
                    finished_at = now(),
                    outcome = 'success',
                    error_stage = CAST(NULL AS worker_execution_error_stage_enum),
                    error_message = NULL,
                    embeddings_count = :embeddings_count,
                    processing_seconds = NULL
                WHERE id = :execution_id
                """
            ),
            {
                "execution_id": execution_id,
                "embeddings_count": task_summary["sources_processed"],
            },
        )
        _refresh_worker_job_status(db, job_id=str(row["job_id"]))
        db.commit()
    except Exception as exception:
        db.rollback()
        raise RuntimeError(f"Unable to complete embedding task {task_id}: {exception}") from exception
    finally:
        db.close()


def fail_embedding_task(
    *,
    worker_identity_id: int,
    worker_id: str,
    task_id: int,
    execution_id: int,
    error_message: str,
) -> None:
    db = open_db_session()
    try:
        current_worker_instance_id = upsert_worker_instance_state(
            db,
            identity_id=worker_identity_id,
            worker_type=WORKER_TYPE_SOURCE_EMBEDDING,
            worker_name=worker_id,
            active=True,
            pending_tasks=0,
            connection_state="connected",
            desired_state="running",
            current_task_id=None,
            current_execution_id=None,
            current_task_label=None,
            current_feed_id=None,
            current_feed_url=None,
            last_error=error_message[:4000],
        )
        row = _get_execution_row(db, task_id=task_id, execution_id=execution_id)
        if current_worker_instance_id != int(row["worker_instance_id"]):
            raise RuntimeError(
                f"Embedding task {task_id} execution {execution_id} is not owned by worker {worker_id}"
            )

        db.execute(
            text(
                """
                UPDATE source_embedding_task_items
                SET
                    status = 'error',
                    error_message = :error_message,
                    completed_at = COALESCE(completed_at, now())
                WHERE task_id = :task_id
                    AND status = 'pending'
                """
            ),
            {
                "task_id": task_id,
                "error_message": error_message[:4000],
            },
        )
        task_summary = _refresh_embedding_task_summary(db, task_id=task_id, terminal_status="failed")
        db.execute(
            text(
                """
                UPDATE source_embedding_task_executions
                SET
                    finished_at = now(),
                    outcome = 'error',
                    error_stage = CAST(:error_stage AS worker_execution_error_stage_enum),
                    error_message = :error_message,
                    embeddings_count = :embeddings_count
                WHERE id = :execution_id
                """
            ),
            {
                "execution_id": execution_id,
                "error_stage": _resolve_embedding_error_stage(error_message),
                "error_message": error_message[:4000],
                "embeddings_count": task_summary["sources_processed"],
            },
        )
        _refresh_worker_job_status(db, job_id=str(row["job_id"]))
        db.commit()
    except Exception as exception:
        db.rollback()
        raise RuntimeError(f"Unable to fail embedding task {task_id}: {exception}") from exception
    finally:
        db.close()


def _get_execution_row(db, *, task_id: int, execution_id: int):
    row = db.execute(
        text(
            """
            SELECT
                execution.worker_instance_id,
                task.job_id,
                model.code AS model_name
            FROM source_embedding_task_executions AS execution
            JOIN source_embedding_tasks AS task
                ON task.id = execution.task_id
            JOIN embedding_models AS model
                ON model.id = task.embedding_model_id
            WHERE execution.id = :execution_id
                AND execution.task_id = :task_id
            """
        ),
        {
            "execution_id": execution_id,
            "task_id": task_id,
        },
    ).mappings().first()
    if row is None:
        raise RuntimeError(f"Missing embedding execution {execution_id} for task {task_id}")
    return row


def _list_task_source_ids(db, *, task_id: int) -> set[int]:
    rows = db.execute(
        text(
            """
            SELECT source_id
            FROM source_embedding_task_items
            WHERE task_id = :task_id
            """
        ),
        {"task_id": task_id},
    ).scalars().all()
    return {int(source_id) for source_id in rows}


def _refresh_embedding_task_summary(
    db,
    *,
    task_id: int,
    terminal_status: str,
) -> dict[str, int]:
    row = db.execute(
        text(
            """
            SELECT
                COUNT(*) AS sources_total,
                COUNT(*) FILTER (WHERE status <> 'pending') AS sources_processed,
                COUNT(*) FILTER (WHERE status = 'success') AS sources_success,
                COUNT(*) FILTER (WHERE status = 'error') AS sources_error
            FROM source_embedding_task_items
            WHERE task_id = :task_id
            """
        ),
        {"task_id": task_id},
    ).mappings().one()

    summary = {
        "sources_total": int(row["sources_total"] or 0),
        "sources_processed": int(row["sources_processed"] or 0),
        "sources_success": int(row["sources_success"] or 0),
        "sources_error": int(row["sources_error"] or 0),
    }
    db.execute(
        text(
            """
            UPDATE source_embedding_tasks
            SET
                status = CAST(:status AS worker_task_status_enum),
                claim_expires_at = NULL,
                completed_at = CASE
                    WHEN :status IN ('completed', 'failed') THEN now()
                    ELSE NULL
                END,
                sources_total = :sources_total,
                sources_processed = :sources_processed,
                sources_success = :sources_success,
                sources_error = :sources_error,
                updated_at = now()
            WHERE id = :task_id
            """
        ),
        {
            "task_id": task_id,
            "status": terminal_status,
            **summary,
        },
    )
    return summary


def _refresh_worker_job_status(db, *, job_id: str) -> None:
    row = db.execute(
        text(
            """
            SELECT
                COUNT(task.id) AS tasks_total,
                COUNT(task.id) FILTER (WHERE task.status IN ('completed', 'failed')) AS tasks_processed,
                COUNT(item.source_id) AS items_total,
                COUNT(item.source_id) FILTER (WHERE item.status <> 'pending') AS items_processed,
                COUNT(item.source_id) FILTER (WHERE item.status = 'success') AS items_success,
                COUNT(item.source_id) FILTER (WHERE item.status = 'error') AS items_error,
                COUNT(task.id) FILTER (WHERE task.status = 'processing') AS processing_count,
                COUNT(task.id) FILTER (WHERE task.status = 'pending') AS pending_count,
                COUNT(task.id) FILTER (WHERE task.status = 'failed') AS failed_task_count
            FROM source_embedding_tasks AS task
            LEFT JOIN source_embedding_task_items AS item
                ON item.task_id = task.id
            WHERE task.job_id = :job_id
            """
        ),
        {"job_id": job_id},
    ).mappings().one()

    tasks_total = int(row["tasks_total"] or 0)
    tasks_processed = int(row["tasks_processed"] or 0)
    items_total = int(row["items_total"] or 0)
    items_processed = int(row["items_processed"] or 0)
    items_success = int(row["items_success"] or 0)
    items_error = int(row["items_error"] or 0)
    processing_count = int(row["processing_count"] or 0)
    pending_count = int(row["pending_count"] or 0)
    failed_task_count = int(row["failed_task_count"] or 0)

    if tasks_total == 0:
        status = "completed"
    elif processing_count > 0 or (tasks_processed > 0 and pending_count > 0):
        status = "processing"
    elif pending_count == tasks_total:
        status = "queued"
    elif items_error > 0 or failed_task_count > 0:
        status = "completed_with_errors"
    else:
        status = "completed"

    db.execute(
        text(
            """
            UPDATE worker_jobs
            SET
                status = CAST(:status AS worker_job_status_enum),
                tasks_total = :tasks_total,
                tasks_processed = :tasks_processed,
                items_total = :items_total,
                items_processed = :items_processed,
                items_success = :items_success,
                items_error = :items_error,
                started_at = CASE
                    WHEN :status <> 'queued' THEN COALESCE(started_at, now())
                    ELSE started_at
                END,
                finished_at = CASE
                    WHEN :status IN ('completed', 'completed_with_errors', 'failed') THEN now()
                    ELSE NULL
                END,
                updated_at = now()
            WHERE id = :job_id
            """
        ),
        {
            "job_id": job_id,
            "status": status,
            "tasks_total": tasks_total,
            "tasks_processed": tasks_processed,
            "items_total": items_total,
            "items_processed": items_processed,
            "items_success": items_success,
            "items_error": items_error,
        },
    )


def _resolve_embedding_error_stage(error_message: str) -> str:
    normalized_error = error_message.lower()
    if normalized_error.startswith("invalid payload"):
        return "invalid_payload"
    return "embedding"
