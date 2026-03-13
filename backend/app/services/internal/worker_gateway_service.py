from __future__ import annotations

from fastapi import HTTPException

from app.schemas.internal import (
    EmbeddingTaskCompleteRequestSchema,
    EmbeddingTaskFailRequestSchema,
    RssTaskCompleteRequestSchema,
    RssWorkerStateRequestSchema,
    WorkerTaskClaimRead,
    WorkerTaskClaimRequestSchema,
    WorkerTaskCommandRead,
    WorkerTaskFailRequestSchema,
)
from .rss_worker_task_service import (
    claim_scrape_tasks,
    complete_scrape_task,
    fail_scrape_task,
    update_worker_state,
)
from .source_embedding_worker_task_service import (
    claim_embedding_tasks as claim_source_embedding_tasks,
    complete_embedding_task as complete_source_embedding_task,
    fail_embedding_task as fail_source_embedding_task,
)
from .worker_auth_service import AuthenticatedWorkerContext


def claim_rss_tasks(
    *,
    worker: AuthenticatedWorkerContext,
    payload: WorkerTaskClaimRequestSchema,
) -> list[WorkerTaskClaimRead]:
    _require_worker_type(worker, "rss_scrapper")
    tasks = claim_scrape_tasks(
        worker_identity_id=worker.identity_id,
        worker_id=worker.device_id,
        count=payload.count,
        lease_seconds=payload.lease_seconds,
    )
    return [
        WorkerTaskClaimRead(
            task_id=task_id,
            execution_id=execution_id,
            payload=payload,
        )
        for task_id, execution_id, payload in tasks
    ]


def complete_rss_task(
    *,
    worker: AuthenticatedWorkerContext,
    payload: RssTaskCompleteRequestSchema,
) -> WorkerTaskCommandRead:
    _require_worker_type(worker, "rss_scrapper")
    complete_scrape_task(
        worker_identity_id=worker.identity_id,
        worker_id=worker.device_id,
        task_id=payload.task_id,
        execution_id=payload.execution_id,
        result_events=payload.result_events,
    )
    return WorkerTaskCommandRead(ok=True)


def fail_rss_task(
    *,
    worker: AuthenticatedWorkerContext,
    payload: WorkerTaskFailRequestSchema,
) -> WorkerTaskCommandRead:
    _require_worker_type(worker, "rss_scrapper")
    fail_scrape_task(
        worker_identity_id=worker.identity_id,
        worker_id=worker.device_id,
        task_id=payload.task_id,
        execution_id=payload.execution_id,
        error_message=payload.error_message,
    )
    return WorkerTaskCommandRead(ok=True)


def update_rss_state(
    *,
    worker: AuthenticatedWorkerContext,
    payload: RssWorkerStateRequestSchema,
) -> WorkerTaskCommandRead:
    _require_worker_type(worker, "rss_scrapper")
    update_worker_state(
        worker_identity_id=worker.identity_id,
        worker_id=worker.device_id,
        active=payload.active,
        connection_state=payload.connection_state,
        pending_tasks=payload.pending_tasks,
        current_task_id=payload.current_task_id,
        current_execution_id=payload.current_execution_id,
        current_task_label=payload.current_task_label,
        current_feed_id=payload.current_feed_id,
        current_feed_url=payload.current_feed_url,
        last_error=payload.last_error,
        desired_state=payload.desired_state,
    )
    return WorkerTaskCommandRead(ok=True)


def claim_embedding_tasks(
    *,
    worker: AuthenticatedWorkerContext,
    payload: WorkerTaskClaimRequestSchema,
) -> list[WorkerTaskClaimRead]:
    _require_worker_type(worker, "source_embedding")
    tasks = claim_source_embedding_tasks(
        worker_identity_id=worker.identity_id,
        worker_id=worker.device_id,
        count=payload.count,
        lease_seconds=payload.lease_seconds,
    )
    return [
        WorkerTaskClaimRead(
            task_id=task_id,
            execution_id=execution_id,
            payload=payload,
        )
        for task_id, execution_id, payload in tasks
    ]


def complete_embedding_task(
    *,
    worker: AuthenticatedWorkerContext,
    payload: EmbeddingTaskCompleteRequestSchema,
) -> WorkerTaskCommandRead:
    _require_worker_type(worker, "source_embedding")
    complete_source_embedding_task(
        worker_identity_id=worker.identity_id,
        worker_id=worker.device_id,
        task_id=payload.task_id,
        execution_id=payload.execution_id,
        result_payload=payload.result_payload,
    )
    return WorkerTaskCommandRead(ok=True)


def fail_embedding_task(
    *,
    worker: AuthenticatedWorkerContext,
    payload: EmbeddingTaskFailRequestSchema,
) -> WorkerTaskCommandRead:
    _require_worker_type(worker, "source_embedding")
    fail_source_embedding_task(
        worker_identity_id=worker.identity_id,
        worker_id=worker.device_id,
        task_id=payload.task_id,
        execution_id=payload.execution_id,
        error_message=payload.error_message,
    )
    return WorkerTaskCommandRead(ok=True)


def _require_worker_type(worker: AuthenticatedWorkerContext, expected_worker_type: str) -> None:
    if worker.worker_type != expected_worker_type:
        raise HTTPException(status_code=403, detail="Worker token cannot access this endpoint")
