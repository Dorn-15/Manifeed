from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.sources import (
    RssSourceEmbeddingMapPointRead,
    RssSourceEmbeddingSimilarityCandidateSchema,
)


def list_rss_source_embedding_map_points(
    db: Session,
    *,
    model_name: str,
    published_from: datetime | None = None,
    published_to_exclusive: datetime | None = None,
) -> tuple[list[RssSourceEmbeddingMapPointRead], int, str]:
    filter_sql, filter_params = _build_published_at_filters(
        published_from=published_from,
        published_to_exclusive=published_to_exclusive,
        source_alias="source",
    )
    total = int(
        db.execute(
            text(
                f"""
                SELECT count(*)
                FROM rss_source_embedding_layouts AS layout
                JOIN embedding_models AS model
                    ON model.id = layout.embedding_model_id
                JOIN rss_sources AS source
                    ON source.id = layout.source_id
                WHERE model.code = :model_name
                {filter_sql}
                """
            ),
            {
                "model_name": model_name,
                **filter_params,
            },
        ).scalar_one()
        or 0
    )
    if total == 0:
        return [], 0, ""

    rows = (
        db.execute(
            text(
                f"""
                SELECT
                    layout.source_id,
                    layout.x,
                    layout.y,
                    layout.projection_version,
                    source.url,
                    source.published_at,
                    content.title,
                    content.summary,
                    content.image_url
                FROM rss_source_embedding_layouts AS layout
                JOIN embedding_models AS model
                    ON model.id = layout.embedding_model_id
                JOIN rss_sources AS source
                    ON source.id = layout.source_id
                LEFT JOIN rss_source_contents AS content
                    ON content.source_id = source.id
                    AND content.ingested_at = source.ingested_at
                WHERE model.code = :model_name
                {filter_sql}
                ORDER BY layout.embedding_updated_at DESC, layout.source_id DESC
                """
            ),
            {
                "model_name": model_name,
                **filter_params,
            },
        )
        .mappings()
        .all()
    )
    source_ids = [int(row["source_id"]) for row in rows]
    company_names_by_source_id = _list_company_names_by_source_ids(db, source_ids=source_ids)

    items: list[RssSourceEmbeddingMapPointRead] = []
    projection_version = ""
    for row in rows:
        projection_version = str(row["projection_version"])
        source_id = int(row["source_id"])
        items.append(
            RssSourceEmbeddingMapPointRead(
                source_id=source_id,
                title=str(row["title"]),
                summary=(str(row["summary"]) if row["summary"] is not None else None),
                url=str(row["url"]),
                published_at=row["published_at"],
                image_url=(str(row["image_url"]) if row["image_url"] is not None else None),
                company_names=company_names_by_source_id.get(source_id, []),
                x=float(row["x"]),
                y=float(row["y"]),
            )
        )
    return items, total, projection_version


def get_rss_source_embedding_similarity_candidate(
    db: Session,
    *,
    source_id: int,
    model_name: str,
    published_from: datetime | None = None,
    published_to_exclusive: datetime | None = None,
) -> RssSourceEmbeddingSimilarityCandidateSchema | None:
    rows = _list_similarity_candidate_rows(
        db,
        model_name=model_name,
        source_ids=[source_id],
        published_from=published_from,
        published_to_exclusive=published_to_exclusive,
    )
    if not rows:
        return None
    return rows[0]


def list_rss_source_embedding_neighbors(
    db: Session,
    *,
    source_id: int,
    neighbor_limit: int,
    model_name: str,
    published_from: datetime | None = None,
    published_to_exclusive: datetime | None = None,
) -> list[RssSourceEmbeddingSimilarityCandidateSchema]:
    filter_sql, filter_params = _build_published_at_filters(
        published_from=published_from,
        published_to_exclusive=published_to_exclusive,
        source_alias="source",
    )
    query = f"""
        WITH anchor AS (
            SELECT
                layout.source_id,
                embedding.embedding AS anchor_embedding
            FROM rss_source_embedding_layouts AS layout
            JOIN embedding_models AS model
                ON model.id = layout.embedding_model_id
            JOIN rss_source_embeddings AS embedding
                ON embedding.source_id = layout.source_id
                AND embedding.embedding_model_id = layout.embedding_model_id
            JOIN rss_sources AS source
                ON source.id = layout.source_id
            WHERE model.code = :model_name
                AND layout.source_id = :source_id
                {filter_sql}
            LIMIT 1
        )
        SELECT
            layout.source_id,
            layout.x,
            layout.y,
            layout.projection_version,
            source.url,
            source.published_at,
            content.title,
            content.summary,
            content.image_url,
            embedding.embedding,
            COALESCE(
                (
                    SELECT SUM(candidate_vector.value * anchor_vector.value)
                    FROM unnest(embedding.embedding) WITH ORDINALITY AS candidate_vector(value, index_id)
                    JOIN unnest(anchor.anchor_embedding) WITH ORDINALITY AS anchor_vector(value, index_id)
                        USING (index_id)
                ),
                0.0
            ) AS similarity
        FROM rss_source_embedding_layouts AS layout
        JOIN anchor
            ON TRUE
        JOIN embedding_models AS model
            ON model.id = layout.embedding_model_id
        JOIN rss_source_embeddings AS embedding
            ON embedding.source_id = layout.source_id
            AND embedding.embedding_model_id = layout.embedding_model_id
        JOIN rss_sources AS source
            ON source.id = layout.source_id
        LEFT JOIN rss_source_contents AS content
            ON content.source_id = source.id
            AND content.ingested_at = source.ingested_at
        WHERE model.code = :model_name
            AND layout.source_id <> :source_id
            {filter_sql}
    """
    params: dict[str, object] = {
        "model_name": model_name,
        "source_id": source_id,
        "neighbor_limit": neighbor_limit,
        **filter_params,
    }
    query += " ORDER BY similarity DESC, layout.source_id DESC LIMIT :neighbor_limit"

    rows = db.execute(text(query), params).mappings().all()
    source_ids_from_rows = [int(row["source_id"]) for row in rows]
    company_names_by_source_id = _list_company_names_by_source_ids(db, source_ids=source_ids_from_rows)
    candidates: list[RssSourceEmbeddingSimilarityCandidateSchema] = []
    for row in rows:
        source_id = int(row["source_id"])
        candidates.append(
            RssSourceEmbeddingSimilarityCandidateSchema(
                source_id=source_id,
                title=str(row["title"]),
                summary=(str(row["summary"]) if row["summary"] is not None else None),
                url=str(row["url"]),
                published_at=row["published_at"],
                image_url=(str(row["image_url"]) if row["image_url"] is not None else None),
                company_names=company_names_by_source_id.get(source_id, []),
                x=float(row["x"]),
                y=float(row["y"]),
                embedding=[float(value) for value in row["embedding"]],
                embedding_model_name=model_name,
                projection_version=str(row["projection_version"]),
                similarity=float(row["similarity"]),
            )
        )
    return candidates


def _list_company_names_by_source_ids(
    db: Session,
    *,
    source_ids: Sequence[int],
) -> dict[int, list[str]]:
    unique_source_ids = sorted({int(source_id) for source_id in source_ids if int(source_id) > 0})
    if not unique_source_ids:
        return {}

    rows = (
        db.execute(
            text(
                """
                SELECT
                    source_feed.source_id,
                    company.name
                FROM rss_source_feeds AS source_feed
                JOIN rss_feeds AS feed
                    ON feed.id = source_feed.feed_id
                JOIN rss_company AS company
                    ON company.id = feed.company_id
                WHERE source_feed.source_id = ANY(:source_ids)
                    AND company.name IS NOT NULL
                ORDER BY source_feed.source_id ASC, company.name ASC
                """
            ),
            {
                "source_ids": unique_source_ids,
            },
        )
        .mappings()
        .all()
    )

    company_names_by_source_id: dict[int, list[str]] = {
        source_id: [] for source_id in unique_source_ids
    }
    for row in rows:
        source_id = int(row["source_id"])
        company_name = str(row["name"])
        existing_names = company_names_by_source_id.setdefault(source_id, [])
        if company_name not in existing_names:
            existing_names.append(company_name)
    return company_names_by_source_id


def _list_similarity_candidate_rows(
    db: Session,
    *,
    model_name: str,
    source_ids: Sequence[int] | None = None,
    published_from: datetime | None = None,
    published_to_exclusive: datetime | None = None,
) -> list[RssSourceEmbeddingSimilarityCandidateSchema]:
    filter_sql, filter_params = _build_published_at_filters(
        published_from=published_from,
        published_to_exclusive=published_to_exclusive,
        source_alias="source",
    )
    query = f"""
        SELECT
            layout.source_id,
            layout.x,
            layout.y,
            layout.projection_version,
            source.url,
            source.published_at,
            content.title,
            content.summary,
            content.image_url,
            embedding.embedding
        FROM rss_source_embedding_layouts AS layout
        JOIN embedding_models AS model
            ON model.id = layout.embedding_model_id
        JOIN rss_source_embeddings AS embedding
            ON embedding.source_id = layout.source_id
            AND embedding.embedding_model_id = layout.embedding_model_id
        JOIN rss_sources AS source
            ON source.id = layout.source_id
        LEFT JOIN rss_source_contents AS content
            ON content.source_id = source.id
            AND content.ingested_at = source.ingested_at
        WHERE model.code = :model_name
            {filter_sql}
    """
    params: dict[str, object] = {
        "model_name": model_name,
        **filter_params,
    }
    if source_ids:
        query += " AND layout.source_id = ANY(:source_ids)"
        params["source_ids"] = list(source_ids)
    query += " ORDER BY layout.embedding_updated_at DESC, layout.source_id DESC"

    rows = db.execute(text(query), params).mappings().all()
    source_ids_from_rows = [int(row["source_id"]) for row in rows]
    company_names_by_source_id = _list_company_names_by_source_ids(db, source_ids=source_ids_from_rows)
    candidates: list[RssSourceEmbeddingSimilarityCandidateSchema] = []
    for row in rows:
        source_id = int(row["source_id"])
        candidates.append(
            RssSourceEmbeddingSimilarityCandidateSchema(
                source_id=source_id,
                title=str(row["title"]),
                summary=(str(row["summary"]) if row["summary"] is not None else None),
                url=str(row["url"]),
                published_at=row["published_at"],
                image_url=(str(row["image_url"]) if row["image_url"] is not None else None),
                company_names=company_names_by_source_id.get(source_id, []),
                x=float(row["x"]),
                y=float(row["y"]),
                embedding=[float(value) for value in row["embedding"]],
                embedding_model_name=model_name,
                projection_version=str(row["projection_version"]),
            )
        )
    return candidates


def _build_published_at_filters(
    *,
    published_from: datetime | None,
    published_to_exclusive: datetime | None,
    source_alias: str,
) -> tuple[str, dict[str, datetime]]:
    filters: list[str] = []
    params: dict[str, datetime] = {}
    if published_from is not None:
        filters.append(f"AND {source_alias}.published_at >= :published_from")
        params["published_from"] = published_from
    if published_to_exclusive is not None:
        filters.append(f"AND {source_alias}.published_at < :published_to_exclusive")
        params["published_to_exclusive"] = published_to_exclusive
    return "\n                ".join(filters), params
