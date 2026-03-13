from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.schemas.internal import (
    EmbeddingTaskCompleteRequestSchema,
    EmbeddingTaskFailRequestSchema,
    QueueOverviewRead,
    QueuePurgeRead,
    RssTaskCompleteRequestSchema,
    RssWorkerStateRequestSchema,
    WorkerAuthChallengeRead,
    WorkerAuthChallengeRequestSchema,
    WorkerAuthVerifyRequestSchema,
    WorkerMeRead,
    WorkerOverviewRead,
    WorkerSessionRead,
    WorkerTaskClaimRead,
    WorkerTaskClaimRequestSchema,
    WorkerTaskCommandRead,
    WorkerTaskFailRequestSchema,
    WorkerEnrollRequestSchema,
)
from app.services.internal import (
    claim_embedding_tasks,
    claim_rss_tasks,
    complete_embedding_task,
    complete_rss_task,
    enroll_worker_identity,
    fail_embedding_task,
    fail_rss_task,
    get_queues_overview,
    get_workers_overview,
    issue_worker_auth_challenge,
    purge_task_queue,
    read_current_worker_profile,
    require_authenticated_worker_context,
    update_rss_state,
    verify_worker_auth_challenge,
)
from database import get_db_session

internal_workers_router = APIRouter(prefix="/internal/workers", tags=["internal-workers"])


@internal_workers_router.post("/enroll", response_model=WorkerAuthChallengeRead)
def enroll_worker(
    payload: WorkerEnrollRequestSchema,
    db: Session = Depends(get_db_session),
) -> WorkerAuthChallengeRead:
    return enroll_worker_identity(payload, db)


@internal_workers_router.post("/auth/challenge", response_model=WorkerAuthChallengeRead)
def request_worker_auth_challenge(
    payload: WorkerAuthChallengeRequestSchema,
    db: Session = Depends(get_db_session),
) -> WorkerAuthChallengeRead:
    return issue_worker_auth_challenge(payload, db)


@internal_workers_router.post("/auth/verify", response_model=WorkerSessionRead)
def verify_worker_auth(
    payload: WorkerAuthVerifyRequestSchema,
    db: Session = Depends(get_db_session),
) -> WorkerSessionRead:
    return verify_worker_auth_challenge(payload, db)


@internal_workers_router.get("/me", response_model=WorkerMeRead)
def read_worker_me(
    worker=Depends(require_authenticated_worker_context),
    db: Session = Depends(get_db_session),
) -> WorkerMeRead:
    return read_current_worker_profile(db, worker=worker)


@internal_workers_router.post("/rss/claim", response_model=list[WorkerTaskClaimRead])
def claim_rss_tasks_for_worker(
    payload: WorkerTaskClaimRequestSchema,
    worker=Depends(require_authenticated_worker_context),
) -> list[WorkerTaskClaimRead]:
    return claim_rss_tasks(worker=worker, payload=payload)


@internal_workers_router.post("/rss/complete", response_model=WorkerTaskCommandRead)
def complete_rss_task_for_worker(
    payload: RssTaskCompleteRequestSchema,
    worker=Depends(require_authenticated_worker_context),
) -> WorkerTaskCommandRead:
    return complete_rss_task(worker=worker, payload=payload)


@internal_workers_router.post("/rss/fail", response_model=WorkerTaskCommandRead)
def fail_rss_task_for_worker(
    payload: WorkerTaskFailRequestSchema,
    worker=Depends(require_authenticated_worker_context),
) -> WorkerTaskCommandRead:
    return fail_rss_task(worker=worker, payload=payload)


@internal_workers_router.post("/rss/state", response_model=WorkerTaskCommandRead)
def update_rss_state_for_worker(
    payload: RssWorkerStateRequestSchema,
    worker=Depends(require_authenticated_worker_context),
) -> WorkerTaskCommandRead:
    return update_rss_state(worker=worker, payload=payload)


@internal_workers_router.post("/embedding/claim", response_model=list[WorkerTaskClaimRead])
def claim_embedding_tasks_for_worker(
    payload: WorkerTaskClaimRequestSchema,
    worker=Depends(require_authenticated_worker_context),
) -> list[WorkerTaskClaimRead]:
    return claim_embedding_tasks(worker=worker, payload=payload)


@internal_workers_router.post("/embedding/complete", response_model=WorkerTaskCommandRead)
def complete_embedding_task_for_worker(
    payload: EmbeddingTaskCompleteRequestSchema,
    worker=Depends(require_authenticated_worker_context),
) -> WorkerTaskCommandRead:
    return complete_embedding_task(worker=worker, payload=payload)


@internal_workers_router.post("/embedding/fail", response_model=WorkerTaskCommandRead)
def fail_embedding_task_for_worker(
    payload: EmbeddingTaskFailRequestSchema,
    worker=Depends(require_authenticated_worker_context),
) -> WorkerTaskCommandRead:
    return fail_embedding_task(worker=worker, payload=payload)


@internal_workers_router.get("/overview", response_model=WorkerOverviewRead)
def read_workers_overview(db: Session = Depends(get_db_session)) -> WorkerOverviewRead:
    return get_workers_overview(db)


@internal_workers_router.get("/queues/overview", response_model=QueueOverviewRead)
def read_queues_overview(db: Session = Depends(get_db_session)) -> QueueOverviewRead:
    return get_queues_overview(db)


@internal_workers_router.post("/queues/{queue_name}/purge", response_model=QueuePurgeRead)
def purge_task_queue_by_name(
    queue_name: str = Path(min_length=1),
    db: Session = Depends(get_db_session),
) -> QueuePurgeRead:
    return purge_task_queue(db, queue_name)
