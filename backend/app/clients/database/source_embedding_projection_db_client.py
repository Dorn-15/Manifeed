from __future__ import annotations
from collections.abc import Sequence
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.source_embedding_projection_schema import (
    SourceEmbeddingProjectionInputSchema,
    SourceEmbeddingProjectionPointSchema,
    SourceEmbeddingProjectionStateSchema,
)


def list_source_embedding_model_names(
    db: Session,
) -> list[str]:
    rows = (
        db.execute(
            text(
                """
                SELECT DISTINCT model.code
                FROM rss_source_embeddings AS embedding
                JOIN embedding_models AS model
                    ON model.id = embedding.embedding_model_id
                ORDER BY model.code ASC
                """
            )
        )
        .scalars()
        .all()
    )
    return [str(row) for row in rows]


def count_source_embedding_projection_inputs(
    db: Session,
    *,
    model_name: str,
) -> int:
    return int(
        db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM rss_source_embeddings AS embedding
                JOIN embedding_models AS model
                    ON model.id = embedding.embedding_model_id
                WHERE model.code = :model_name
                """
            ),
            {"model_name": model_name},
        ).scalar_one()
        or 0
    )


def list_source_embedding_projection_inputs(
    db: Session,
    *,
    model_name: str,
    source_ids: Sequence[int] | None = None,
) -> list[SourceEmbeddingProjectionInputSchema]:
    query = """
        SELECT
            embedding.source_id,
            embedding.embedding,
            embedding.updated_at
        FROM rss_source_embeddings AS embedding
        JOIN embedding_models AS model
            ON model.id = embedding.embedding_model_id
        WHERE model.code = :model_name
    """
    params: dict[str, object] = {"model_name": model_name}
    if source_ids:
        query += " AND embedding.source_id = ANY(:source_ids)"
        params["source_ids"] = list(source_ids)
    query += " ORDER BY embedding.source_id ASC"

    rows = db.execute(text(query), params).mappings().all()
    return [
        SourceEmbeddingProjectionInputSchema(
            source_id=int(row["source_id"]),
            embedding=[float(value) for value in row["embedding"]],
            embedding_updated_at=_normalize_datetime(row["updated_at"]),
        )
        for row in rows
    ]


def list_source_embedding_projection_input_batch(
    db: Session,
    *,
    model_name: str,
    limit: int,
    after_source_id: int | None = None,
) -> list[SourceEmbeddingProjectionInputSchema]:
    query = """
        SELECT
            embedding.source_id,
            embedding.embedding,
            embedding.updated_at
        FROM rss_source_embeddings AS embedding
        JOIN embedding_models AS model
            ON model.id = embedding.embedding_model_id
        WHERE model.code = :model_name
    """
    params: dict[str, object] = {
        "model_name": model_name,
        "limit": limit,
    }
    if after_source_id is not None:
        query += " AND embedding.source_id > :after_source_id"
        params["after_source_id"] = after_source_id
    query += " ORDER BY embedding.source_id ASC LIMIT :limit"

    rows = db.execute(text(query), params).mappings().all()
    return [
        SourceEmbeddingProjectionInputSchema(
            source_id=int(row["source_id"]),
            embedding=[float(value) for value in row["embedding"]],
            embedding_updated_at=_normalize_datetime(row["updated_at"]),
        )
        for row in rows
    ]


def list_source_embedding_projection_sample_inputs(
    db: Session,
    *,
    model_name: str,
    limit: int,
) -> list[SourceEmbeddingProjectionInputSchema]:
    rows = (
        db.execute(
            text(
                """
                SELECT
                    embedding.source_id,
                    embedding.embedding,
                    embedding.updated_at
                FROM rss_source_embeddings AS embedding
                JOIN embedding_models AS model
                    ON model.id = embedding.embedding_model_id
                WHERE model.code = :model_name
                ORDER BY md5(embedding.source_id::text) ASC, embedding.source_id ASC
                LIMIT :limit
                """
            ),
            {
                "model_name": model_name,
                "limit": limit,
            },
        )
        .mappings()
        .all()
    )
    return [
        SourceEmbeddingProjectionInputSchema(
            source_id=int(row["source_id"]),
            embedding=[float(value) for value in row["embedding"]],
            embedding_updated_at=_normalize_datetime(row["updated_at"]),
        )
        for row in rows
    ]


def get_source_embedding_projection_state(
    db: Session,
    *,
    model_name: str,
) -> SourceEmbeddingProjectionStateSchema | None:
    row = (
        db.execute(
            text(
                """
                SELECT
                    model.code AS embedding_model_name,
                    state.projection_version,
                    state.projector_kind,
                    state.projector_state,
                    state.fitted_sources_count,
                    state.last_embedding_updated_at,
                    state.updated_at
                FROM rss_source_embedding_projection_states AS state
                JOIN embedding_models AS model
                    ON model.id = state.embedding_model_id
                WHERE model.code = :model_name
                """
            ),
            {"model_name": model_name},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None

    return SourceEmbeddingProjectionStateSchema(
        embedding_model_name=str(row["embedding_model_name"]),
        projection_version=str(row["projection_version"]),
        projector_kind=str(row["projector_kind"]),
        projector_state=bytes(row["projector_state"]),
        fitted_sources_count=int(row["fitted_sources_count"]),
        last_embedding_updated_at=_normalize_datetime(row["last_embedding_updated_at"])
        if row["last_embedding_updated_at"] is not None
        else None,
        updated_at=_normalize_datetime(row["updated_at"]),
    )


def get_source_embedding_latest_update_at(
    db: Session,
    *,
    model_name: str,
) -> datetime | None:
    value = db.execute(
        text(
            """
            SELECT MAX(embedding.updated_at)
            FROM rss_source_embeddings AS embedding
            JOIN embedding_models AS model
                ON model.id = embedding.embedding_model_id
            WHERE model.code = :model_name
            """
        ),
        {"model_name": model_name},
    ).scalar_one_or_none()
    if value is None:
        return None
    return _normalize_datetime(value)


def upsert_source_embedding_projection_state(
    db: Session,
    *,
    state: SourceEmbeddingProjectionStateSchema,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO rss_source_embedding_projection_states (
                embedding_model_id,
                projection_version,
                projector_kind,
                projector_state,
                fitted_sources_count,
                last_embedding_updated_at,
                updated_at
            )
            SELECT
                model.id,
                :projection_version,
                :projector_kind,
                :projector_state,
                :fitted_sources_count,
                :last_embedding_updated_at,
                now()
            FROM embedding_models AS model
            WHERE model.code = :embedding_model_name
            ON CONFLICT (embedding_model_id) DO UPDATE SET
                projection_version = EXCLUDED.projection_version,
                projector_kind = EXCLUDED.projector_kind,
                projector_state = EXCLUDED.projector_state,
                fitted_sources_count = EXCLUDED.fitted_sources_count,
                last_embedding_updated_at = EXCLUDED.last_embedding_updated_at,
                updated_at = now()
            """
        ),
        {
            **state.model_dump(),
            "last_embedding_updated_at": state.last_embedding_updated_at,
        },
    )


def upsert_source_embedding_projection_points(
    db: Session,
    *,
    points: Sequence[SourceEmbeddingProjectionPointSchema],
) -> None:
    for point in points:
        db.execute(
            text(
                """
                INSERT INTO rss_source_embedding_layouts (
                    source_id,
                    embedding_model_id,
                    projection_version,
                    x,
                    y,
                    embedding_updated_at,
                    projected_at
                )
                SELECT
                    :source_id,
                    model.id,
                    :projection_version,
                    :x,
                    :y,
                    :embedding_updated_at,
                    now()
                FROM embedding_models AS model
                WHERE model.code = :embedding_model_name
                ON CONFLICT (source_id) DO UPDATE SET
                    embedding_model_id = EXCLUDED.embedding_model_id,
                    projection_version = EXCLUDED.projection_version,
                    x = EXCLUDED.x,
                    y = EXCLUDED.y,
                    embedding_updated_at = EXCLUDED.embedding_updated_at,
                    projected_at = now()
                """
            ),
            point.model_dump(),
        )


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
