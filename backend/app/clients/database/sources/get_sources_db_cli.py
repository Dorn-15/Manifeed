from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.sources import (
    RssSourceDetailRead,
    RssSourceEmbeddingPayloadSchema,
    RssSourceRead,
)

SOURCE_PUBLISHED_AT_FALLBACK = datetime(1970, 1, 1, tzinfo=timezone.utc)


def list_rss_sources_read(
    db: Session,
    *,
    limit: int,
    offset: int,
    feed_id: int | None = None,
    company_id: int | None = None,
) -> tuple[list[RssSourceRead], int]:
    filters, params = _build_source_filters(feed_id=feed_id, company_id=company_id)
    where_sql = ""
    if filters:
        where_sql = "WHERE " + " AND ".join(filters)

    total = int(
        db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM rss_sources AS source
                {where_sql}
                """
            ),
            params,
        ).scalar_one()
        or 0
    )
    if total == 0:
        return [], 0

    rows = (
        db.execute(
            text(
                f"""
                SELECT
                    source.id,
                    source.url,
                    source.published_at,
                    content.title,
                    content.summary,
                    content.author,
                    content.image_url
                FROM rss_sources AS source
                LEFT JOIN rss_source_contents AS content
                    ON content.source_id = source.id
                    AND content.ingested_at = source.ingested_at
                {where_sql}
                ORDER BY source.published_at DESC NULLS LAST, source.id DESC
                LIMIT :limit
                OFFSET :offset
                """
            ),
            {
                **params,
                "limit": limit,
                "offset": offset,
            },
        )
        .mappings()
        .all()
    )
    company_names_by_source_id = _list_company_names_by_source_ids(
        db,
        source_ids=[int(row["id"]) for row in rows],
    )

    return [
        RssSourceRead(
            id=int(row["id"]),
            title=str(row["title"]),
            summary=(str(row["summary"]) if row["summary"] is not None else None),
            author=(str(row["author"]) if row["author"] is not None else None),
            url=str(row["url"]),
            published_at=_to_public_published_at(row["published_at"]),
            image_url=(str(row["image_url"]) if row["image_url"] is not None else None),
            company_names=company_names_by_source_id.get(int(row["id"]), []),
        )
        for row in rows
    ], total


def list_rss_sources_by_urls(
    db: Session,
    urls: Sequence[str],
) -> dict[str, RssSourceRead]:
    unique_urls = sorted({url for url in urls if url})
    if not unique_urls:
        return {}

    rows = (
        db.execute(
            text(
                """
                SELECT DISTINCT ON (source.url)
                    source.id,
                    source.url,
                    source.published_at,
                    content.title,
                    content.summary,
                    content.author,
                    content.image_url
                FROM rss_sources AS source
                LEFT JOIN rss_source_contents AS content
                    ON content.source_id = source.id
                    AND content.ingested_at = source.ingested_at
                WHERE source.url = ANY(:urls)
                ORDER BY source.url ASC, source.published_at DESC NULLS LAST, source.id DESC
                """
            ),
            {"urls": unique_urls},
        )
        .mappings()
        .all()
    )

    return {
        str(row["url"]): RssSourceRead(
            id=int(row["id"]),
            title=str(row["title"]),
            summary=(str(row["summary"]) if row["summary"] is not None else None),
            author=(str(row["author"]) if row["author"] is not None else None),
            url=str(row["url"]),
            published_at=_to_public_published_at(row["published_at"]),
            image_url=(str(row["image_url"]) if row["image_url"] is not None else None),
            company_names=_list_company_names_by_source_ids(db, source_ids=[int(row["id"])]).get(
                int(row["id"]),
                [],
            ),
        )
        for row in rows
    }


def list_rss_sources_without_embeddings(
    db: Session,
    *,
    model_name: str,
    reembed_model_mismatches: bool = False,
) -> list[RssSourceEmbeddingPayloadSchema]:
    rows = (
        db.execute(
            text(
                """
                SELECT
                    source.id,
                    content.title,
                    content.summary,
                    source.url
                FROM rss_sources AS source
                JOIN rss_source_contents AS content
                    ON content.source_id = source.id
                    AND content.ingested_at = source.ingested_at
                LEFT JOIN rss_source_embeddings AS embedding
                    ON embedding.source_id = source.id
                LEFT JOIN embedding_models AS model
                    ON model.id = embedding.embedding_model_id
                WHERE embedding.source_id IS NULL
                    OR (
                        :reembed_model_mismatches = TRUE
                        AND model.code <> :model_name
                    )
                ORDER BY source.id ASC
                """
            ),
            {
                "model_name": model_name,
                "reembed_model_mismatches": reembed_model_mismatches,
            },
        )
        .mappings()
        .all()
    )

    return [
        RssSourceEmbeddingPayloadSchema(
            id=int(row["id"]),
            title=str(row["title"]),
            summary=(str(row["summary"]) if row["summary"] is not None else None),
            url=str(row["url"]),
        )
        for row in rows
    ]


def get_rss_source_detail_read_by_id(
    db: Session,
    source_id: int,
) -> RssSourceDetailRead | None:
    row = (
        db.execute(
            text(
                """
                SELECT
                    source.id,
                    source.url,
                    source.published_at,
                    content.title,
                    content.summary,
                    content.author,
                    content.image_url
                FROM rss_sources AS source
                LEFT JOIN rss_source_contents AS content
                    ON content.source_id = source.id
                    AND content.ingested_at = source.ingested_at
                WHERE source.id = :source_id
                """
            ),
            {"source_id": source_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None

    extra_rows = (
        db.execute(
            text(
                """
                SELECT
                    company.name AS company_name,
                    feed.section AS feed_section
                FROM rss_source_feeds AS source_feed
                JOIN rss_feeds AS feed
                    ON feed.id = source_feed.feed_id
                LEFT JOIN rss_company AS company
                    ON company.id = feed.company_id
                WHERE source_feed.source_id = :source_id
                ORDER BY company.name ASC NULLS LAST, feed.section ASC NULLS LAST
                """
            ),
            {"source_id": source_id},
        )
        .mappings()
        .all()
    )
    company_names = sorted(
        {
            str(extra_row["company_name"])
            for extra_row in extra_rows
            if extra_row["company_name"] is not None
        }
    )
    feed_sections = sorted(
        {
            str(extra_row["feed_section"])
            for extra_row in extra_rows
            if extra_row["feed_section"] is not None
        }
    )

    return RssSourceDetailRead(
        id=int(row["id"]),
        title=str(row["title"]),
        summary=(str(row["summary"]) if row["summary"] is not None else None),
        author=(str(row["author"]) if row["author"] is not None else None),
        url=str(row["url"]),
        published_at=_to_public_published_at(row["published_at"]),
        image_url=(str(row["image_url"]) if row["image_url"] is not None else None),
        company_names=company_names,
        feed_sections=feed_sections,
    )


def _build_source_filters(*, feed_id: int | None, company_id: int | None) -> tuple[list[str], dict[str, object]]:
    filters: list[str] = []
    params: dict[str, object] = {}
    if feed_id is not None:
        filters.append(
            """
            EXISTS (
                SELECT 1
                FROM rss_source_feeds AS source_feed
                WHERE source_feed.source_id = source.id
                    AND source_feed.feed_id = :feed_id
            )
            """
        )
        params["feed_id"] = feed_id
    if company_id is not None:
        filters.append(
            """
            EXISTS (
                SELECT 1
                FROM rss_source_feeds AS source_feed
                JOIN rss_feeds AS feed
                    ON feed.id = source_feed.feed_id
                WHERE source_feed.source_id = source.id
                    AND feed.company_id = :company_id
            )
            """
        )
        params["company_id"] = company_id
    return filters, params


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
            {"source_ids": unique_source_ids},
        )
        .mappings()
        .all()
    )

    company_names_by_source_id: dict[int, list[str]] = {source_id: [] for source_id in unique_source_ids}
    for row in rows:
        source_id = int(row["source_id"])
        company_name = str(row["name"])
        if company_name not in company_names_by_source_id[source_id]:
            company_names_by_source_id[source_id].append(company_name)
    return company_names_by_source_id


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _to_public_published_at(published_at: datetime | None) -> datetime | None:
    normalized = _normalize_datetime(published_at)
    if normalized is None or normalized == SOURCE_PUBLISHED_AT_FALLBACK:
        return None
    return normalized
