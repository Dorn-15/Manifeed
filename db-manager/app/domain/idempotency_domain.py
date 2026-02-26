from __future__ import annotations

from app.schemas import WorkerResultSchema


def build_idempotency_key(payload: WorkerResultSchema) -> tuple[str, int]:
    return payload.job_id, payload.feed_id
