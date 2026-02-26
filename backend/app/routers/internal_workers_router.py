from fastapi import APIRouter

from app.schemas.internal import (
    WorkerTokenRead,
    WorkerTokenRequestSchema,
)
from app.services.internal import issue_worker_access_token

internal_workers_router = APIRouter(prefix="/internal/workers", tags=["internal-workers"])


@internal_workers_router.post("/token", response_model=WorkerTokenRead)
def issue_worker_token(payload: WorkerTokenRequestSchema) -> WorkerTokenRead:
    return issue_worker_access_token(payload)
