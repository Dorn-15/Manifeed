from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas import WorkerEmbeddingResultSchema


def upsert_source_embeddings(
    db: Session,
    *,
    payload: WorkerEmbeddingResultSchema,
) -> None:
    model_id = db.execute(
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
            ON CONFLICT (code) DO UPDATE SET
                updated_at = now()
            RETURNING id
            """
        ),
        {"model_name": payload.model_name},
    ).scalar_one()

    for source in payload.sources:
        db.execute(
            text(
                """
                INSERT INTO rss_source_embeddings (
                    source_id,
                    embedding_model_id,
                    embedding,
                    updated_at
                ) VALUES (
                    :source_id,
                    :embedding_model_id,
                    :embedding,
                    now()
                )
                ON CONFLICT (source_id) DO UPDATE SET
                    embedding_model_id = EXCLUDED.embedding_model_id,
                    embedding = EXCLUDED.embedding,
                    updated_at = now()
                """
            ),
            {
                "source_id": source.id,
                "embedding_model_id": model_id,
                "embedding": source.embedding,
            },
        )

    dimensions = len(payload.sources[0].embedding) if payload.sources else 0
    if dimensions > 0:
        db.execute(
            text(
                """
                UPDATE embedding_models
                SET
                    dimensions = :dimensions,
                    active = TRUE,
                    updated_at = now()
                WHERE id = :model_id
                """
            ),
            {
                "model_id": model_id,
                "dimensions": dimensions,
            },
        )
