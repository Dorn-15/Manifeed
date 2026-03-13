from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.clients.database import (
    create_source_embedding_job,
    enqueue_source_embedding_tasks,
    list_rss_sources_without_embeddings,
    resolve_source_embedding_task_batch_size,
)
from app.schemas.sources import RssSourceEmbeddingEnqueueRead
from app.utils import resolve_embedding_model_name


def enqueue_sources_without_embeddings(
    db: Session,
    *,
    reembed_model_mismatches: bool = False,
) -> RssSourceEmbeddingEnqueueRead:
    model_name = resolve_embedding_model_name()
    sources = list_rss_sources_without_embeddings(
        db,
        model_name=model_name,
        reembed_model_mismatches=reembed_model_mismatches,
    )
    if not sources:
        return RssSourceEmbeddingEnqueueRead(
            job_id=None,
            status="completed",
            tasks_total=0,
            items_total=0,
            queued_sources=0,
        )

    requested_at = datetime.now(timezone.utc)
    tasks_total = _count_batches(
        items_total=len(sources),
        batch_size=resolve_source_embedding_task_batch_size(),
    )
    try:
        job_id = create_source_embedding_job(
            db,
            requested_by="sources_embedding_enqueue_endpoint",
            requested_at=requested_at,
            initial_status="queued",
            tasks_total=tasks_total,
            items_total=len(sources),
        )
        enqueue_source_embedding_tasks(
            db,
            job_id=job_id,
            model_name=model_name,
            requested_at=requested_at,
            sources=sources,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return RssSourceEmbeddingEnqueueRead(
        job_id=job_id,
        status="queued",
        tasks_total=tasks_total,
        items_total=len(sources),
        queued_sources=len(sources),
    )


def _count_batches(*, items_total: int, batch_size: int) -> int:
    if items_total <= 0:
        return 0
    normalized_batch_size = max(1, batch_size)
    return (items_total + normalized_batch_size - 1) // normalized_batch_size
