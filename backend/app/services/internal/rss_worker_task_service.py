from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.clients.database import (
    complete_rss_scrape_task_summary,
    get_worker_instance_id,
    increment_rss_scrape_job_status,
    refresh_rss_scrape_job_status,
    upsert_feed_scraping_state,
    upsert_sources_for_results,
    upsert_worker_instance_state,
)
from database import open_db_session
from app.schemas import WorkerResultSchema

WORKER_TYPE_RSS_SCRAPPER = "rss_scrapper"


def claim_scrape_tasks(
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
            worker_type=WORKER_TYPE_RSS_SCRAPPER,
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
                    FROM rss_scrape_tasks AS task
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
                    UPDATE rss_scrape_tasks AS task
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
                    INSERT INTO rss_scrape_task_executions (
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
                    job.requested_at,
                    job.job_kind,
                    job.requested_by,
                    item.feed_id,
                    item.item_no,
                    feed.url AS feed_url,
                    feed.company_id,
                    company.host AS company_host,
                    COALESCE(feed.fetchprotection_override, company.fetchprotection, 1) AS fetchprotection,
                    runtime.etag,
                    runtime.last_feed_updated_at,
                    runtime.last_db_article_published_at
                FROM executions
                JOIN rss_scrape_tasks AS task
                    ON task.id = executions.task_id
                JOIN worker_jobs AS job
                    ON job.id = task.job_id
                JOIN rss_scrape_task_items AS item
                    ON item.task_id = task.id
                JOIN rss_feeds AS feed
                    ON feed.id = item.feed_id
                LEFT JOIN rss_company AS company
                    ON company.id = feed.company_id
                LEFT JOIN rss_feed_runtime AS runtime
                    ON runtime.feed_id = item.feed_id
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
        raise RuntimeError(f"Unable to claim scrape tasks: {exception}") from exception
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
                "requested_at": row["requested_at"],
                "ingest": row["job_kind"] == "rss_scrape_ingest",
                "requested_by": str(row["requested_by"]),
                "feeds": [],
            }

        assert current_payload is not None
        current_payload["feeds"].append(
            {
                "feed_id": int(row["feed_id"]),
                "feed_url": str(row["feed_url"]),
                "company_id": (int(row["company_id"]) if row["company_id"] is not None else None),
                "host_header": (str(row["company_host"]) if row["company_host"] is not None else None),
                "fetchprotection": int(row["fetchprotection"] or 1),
                "etag": (str(row["etag"]) if row["etag"] is not None else None),
                "last_update": row["last_feed_updated_at"],
                "last_db_article_published_at": row["last_db_article_published_at"],
            }
        )

    if current_task_id is not None and current_execution_id is not None and current_payload is not None:
        claimed_tasks.append((current_task_id, current_execution_id, current_payload))
    return claimed_tasks


def complete_scrape_task(
    *,
    worker_identity_id: int,
    worker_id: str,
    task_id: int,
    execution_id: int,
    result_events: list[dict[str, Any]],
) -> None:
    db = open_db_session()
    try:
        current_worker_instance_id = get_worker_instance_id(
            db,
            worker_type=WORKER_TYPE_RSS_SCRAPPER,
            worker_name=worker_id,
        )
        execution_row = _get_execution_row(db, task_id=task_id, execution_id=execution_id)
        if current_worker_instance_id is None or current_worker_instance_id != int(
            execution_row["worker_instance_id"]
        ):
            raise RuntimeError(
                f"RSS scrape task {task_id} execution {execution_id} is not owned by worker {worker_id}"
            )

        job_id = str(execution_row["job_id"])
        job_kind = str(execution_row["job_kind"])
        should_ingest_sources = job_kind in {"rss_scrape_check", "rss_scrape_ingest"}
        should_update_fetchprotection = job_kind == "rss_scrape_check"
        expected_feed_ids = _list_task_feed_ids(db, task_id=task_id)
        seen_feed_ids: set[int] = set()
        success_feed_count = 0
        error_feed_count = 0
        outcome = "success"
        source_results_to_ingest: list[WorkerResultSchema] = []

        for event in result_events:
            worker_result = WorkerResultSchema.model_validate(_extract_result_payload(event))
            if worker_result.job_id != job_id:
                raise RuntimeError(
                    f"RSS scrape task {task_id} completed with unexpected job_id {worker_result.job_id}"
                )
            if worker_result.feed_id not in expected_feed_ids:
                raise RuntimeError(
                    f"RSS scrape task {task_id} completed an unexpected feed_id {worker_result.feed_id}"
                )
            if worker_result.feed_id in seen_feed_ids:
                raise RuntimeError(
                    f"RSS scrape task {task_id} completed feed_id {worker_result.feed_id} twice"
                )
            seen_feed_ids.add(worker_result.feed_id)
            if worker_result.status == "error":
                outcome = "error"
                error_feed_count += 1
            else:
                success_feed_count += 1

            db.execute(
                text(
                    """
                    UPDATE rss_scrape_task_items
                    SET
                        status = CAST(:status AS rss_scrape_item_status_enum),
                        error_message = :error_message,
                        fetchprotection_used = :fetchprotection_used,
                        new_etag = :new_etag,
                        new_last_update = :new_last_update,
                        sources_count = :sources_count,
                        completed_at = now()
                    WHERE task_id = :task_id
                        AND feed_id = :feed_id
                    """
                ),
                {
                    "task_id": task_id,
                    "feed_id": worker_result.feed_id,
                    "status": worker_result.status,
                    "error_message": worker_result.error_message,
                    "fetchprotection_used": worker_result.fetchprotection,
                    "new_etag": worker_result.new_etag,
                    "new_last_update": worker_result.new_last_update,
                    "sources_count": len(worker_result.sources),
                },
            )
            upsert_feed_scraping_state(
                db,
                payload=worker_result,
                apply_resolved_fetchprotection=should_update_fetchprotection,
            )
            if worker_result.status == "success" and should_ingest_sources:
                source_results_to_ingest.append(worker_result)

        missing_feed_ids = sorted(expected_feed_ids - seen_feed_ids)
        if missing_feed_ids:
            raise RuntimeError(
                f"RSS scrape task {task_id} is missing results for feed_ids {missing_feed_ids}"
            )
        if source_results_to_ingest:
            upsert_sources_for_results(db, payloads=source_results_to_ingest)

        task_summary = complete_rss_scrape_task_summary(
            db,
            task_id=task_id,
            feeds_processed=len(result_events),
            feeds_success=success_feed_count,
            feeds_error=error_feed_count,
        )
        resolved_error_stage = "fetch_feed" if outcome == "error" else None
        resolved_error_message = "One or more feeds failed in batch" if outcome == "error" else None
        db.execute(
            text(
                """
                UPDATE rss_scrape_task_executions
                SET
                    finished_at = now(),
                    outcome = :outcome,
                    error_stage = CAST(:error_stage AS worker_execution_error_stage_enum),
                    error_message = :error_message,
                    processed_feeds_count = :processed_feeds_count
                WHERE id = :execution_id
                """
            ),
            {
                "execution_id": execution_id,
                "outcome": outcome,
                "error_stage": resolved_error_stage,
                "error_message": resolved_error_message,
                "processed_feeds_count": task_summary["feeds_processed"],
            },
        )
        increment_rss_scrape_job_status(
            db,
            job_id=job_id,
            tasks_processed_delta=1,
            items_processed_delta=len(result_events),
            items_success_delta=success_feed_count,
            items_error_delta=error_feed_count,
        )
        db.commit()
    except Exception as exception:
        db.rollback()
        raise RuntimeError(f"Unable to complete scrape task {task_id}: {exception}") from exception
    finally:
        db.close()


def fail_scrape_task(
    *,
    worker_identity_id: int,
    worker_id: str,
    task_id: int,
    execution_id: int,
    error_message: str,
) -> None:
    db = open_db_session()
    try:
        current_worker_instance_id = get_worker_instance_id(
            db,
            worker_type=WORKER_TYPE_RSS_SCRAPPER,
            worker_name=worker_id,
        )
        row = _get_execution_row(db, task_id=task_id, execution_id=execution_id)
        if current_worker_instance_id is None or current_worker_instance_id != int(
            row["worker_instance_id"]
        ):
            raise RuntimeError(
                f"RSS scrape task {task_id} execution {execution_id} is not owned by worker {worker_id}"
            )

        db.execute(
            text(
                """
                UPDATE rss_scrape_task_items
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
        task_summary = _refresh_rss_task_summary(db, task_id=task_id, terminal_status="failed")
        db.execute(
            text(
                """
                UPDATE rss_scrape_task_executions
                SET
                    finished_at = now(),
                    outcome = 'error',
                    error_stage = CAST(:error_stage AS worker_execution_error_stage_enum),
                    error_message = :error_message,
                    processed_feeds_count = :processed_feeds_count
                WHERE id = :execution_id
                """
            ),
            {
                "execution_id": execution_id,
                "error_stage": "worker_loop",
                "error_message": error_message[:4000],
                "processed_feeds_count": task_summary["feeds_processed"],
            },
        )
        refresh_rss_scrape_job_status(db, job_id=str(row["job_id"]))
        db.commit()
    except Exception as exception:
        db.rollback()
        raise RuntimeError(f"Unable to fail scrape task {task_id}: {exception}") from exception
    finally:
        db.close()


def update_worker_state(
    *,
    worker_identity_id: int,
    worker_id: str,
    active: bool,
    connection_state: str,
    pending_tasks: int,
    current_task_id: int | None,
    current_execution_id: int | None,
    current_task_label: str | None,
    current_feed_id: int | None,
    current_feed_url: str | None,
    last_error: str | None,
    desired_state: str | None,
) -> None:
    db = open_db_session()
    try:
        upsert_worker_instance_state(
            db,
            identity_id=worker_identity_id,
            worker_type=WORKER_TYPE_RSS_SCRAPPER,
            worker_name=worker_id,
            active=active,
            pending_tasks=pending_tasks,
            connection_state=connection_state,
            desired_state=desired_state or ("running" if active else "paused"),
            current_task_id=current_task_id,
            current_execution_id=current_execution_id,
            current_task_label=current_task_label,
            current_feed_id=current_feed_id,
            current_feed_url=current_feed_url,
            last_error=last_error,
        )
        db.commit()
    except Exception as exception:
        db.rollback()
        raise RuntimeError(f"Unable to update worker state: {exception}") from exception
    finally:
        db.close()


def _get_execution_row(db, *, task_id: int, execution_id: int):
    row = db.execute(
        text(
            """
            SELECT
                execution.worker_instance_id,
                task.job_id,
                job.job_kind
            FROM rss_scrape_task_executions AS execution
            JOIN rss_scrape_tasks AS task
                ON task.id = execution.task_id
            JOIN worker_jobs AS job
                ON job.id = task.job_id
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
        raise RuntimeError(f"Missing scrape execution {execution_id} for task {task_id}")
    return row


def _list_task_feed_ids(db, *, task_id: int) -> set[int]:
    rows = db.execute(
        text(
            """
            SELECT feed_id
            FROM rss_scrape_task_items
            WHERE task_id = :task_id
            """
        ),
        {"task_id": task_id},
    ).scalars().all()
    return {int(feed_id) for feed_id in rows}


def _extract_result_payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    if isinstance(payload, dict):
        return dict(payload)
    return dict(event)


def _refresh_rss_task_summary(
    db,
    *,
    task_id: int,
    terminal_status: str,
) -> dict[str, int]:
    row = db.execute(
        text(
            """
            SELECT
                COUNT(*) AS feeds_total,
                COUNT(*) FILTER (WHERE status <> 'pending') AS feeds_processed,
                COUNT(*) FILTER (WHERE status IN ('success', 'not_modified')) AS feeds_success,
                COUNT(*) FILTER (WHERE status = 'error') AS feeds_error
            FROM rss_scrape_task_items
            WHERE task_id = :task_id
            """
        ),
        {"task_id": task_id},
    ).mappings().one()

    summary = {
        "feeds_total": int(row["feeds_total"] or 0),
        "feeds_processed": int(row["feeds_processed"] or 0),
        "feeds_success": int(row["feeds_success"] or 0),
        "feeds_error": int(row["feeds_error"] or 0),
    }
    db.execute(
        text(
            """
            UPDATE rss_scrape_tasks
            SET
                status = CAST(:status AS worker_task_status_enum),
                claim_expires_at = NULL,
                completed_at = CASE
                    WHEN :status IN ('completed', 'failed') THEN now()
                    ELSE NULL
                END,
                feeds_total = :feeds_total,
                feeds_processed = :feeds_processed,
                feeds_success = :feeds_success,
                feeds_error = :feeds_error,
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
