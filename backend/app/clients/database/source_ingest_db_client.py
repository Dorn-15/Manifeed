from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas import WorkerResultSchema, WorkerSourceSchema
from app.utils import normalize_article_identity_text

SOURCE_PUBLISHED_AT_FALLBACK = datetime(1970, 1, 1, tzinfo=timezone.utc)
SOURCE_TITLE_MAX_LENGTH = 500
SOURCE_AUTHOR_MAX_LENGTH = 255
SOURCE_IMAGE_URL_MAX_LENGTH = 1000


@dataclass(frozen=True, slots=True)
class _SourceIngestOperation:
    source: WorkerSourceSchema
    feed_id: int
    feed_company_name: str | None


def upsert_sources_for_feed(
    db: Session,
    *,
    payload: WorkerResultSchema,
) -> None:
    upsert_sources_for_results(db, payloads=[payload])


def upsert_sources_for_results(
    db: Session,
    *,
    payloads: list[WorkerResultSchema],
) -> None:
    successful_payloads = [payload for payload in payloads if payload.status == "success"]
    if not successful_payloads:
        return

    feed_company_names = _list_feed_company_names(
        db,
        feed_ids=[payload.feed_id for payload in successful_payloads],
    )
    operations = _build_source_ingest_operations(
        successful_payloads,
        feed_company_names=feed_company_names,
    )
    existing_sources_by_identity = _list_existing_sources_by_identities(
        db,
        identities=[
            _source_identity_key(operation.source.url, operation.source.published_at)
            for operation in operations
        ],
    )
    title_company_cache: dict[tuple[str | None, str | None], dict[str, object] | None] = {}
    resolved_operations: list[tuple[_SourceIngestOperation, dict[str, object]]] = []

    for operation in operations:
        upserted_source = _resolve_or_create_source(
            db,
            url=operation.source.url,
            title=operation.source.title,
            published_at=operation.source.published_at,
            feed_company_name=operation.feed_company_name,
            existing_sources_by_identity=existing_sources_by_identity,
            title_company_cache=title_company_cache,
        )
        resolved_operations.append((operation, upserted_source))

    for operation, upserted_source in resolved_operations:
        source = operation.source
        db.execute(
            text(
                """
                INSERT INTO rss_source_contents (
                    source_id,
                    ingested_at,
                    title,
                    summary,
                    author,
                    image_url
                ) VALUES (
                    :source_id,
                    :ingested_at,
                    :title,
                    :summary,
                    :author,
                    :image_url
                )
                ON CONFLICT (source_id, ingested_at) DO UPDATE SET
                    title = EXCLUDED.title,
                    summary = COALESCE(EXCLUDED.summary, rss_source_contents.summary),
                    author = COALESCE(EXCLUDED.author, rss_source_contents.author),
                    image_url = COALESCE(EXCLUDED.image_url, rss_source_contents.image_url)
                """
            ),
            {
                "source_id": int(upserted_source["id"]),
                "ingested_at": upserted_source["ingested_at"],
                "title": _truncate_required_text(source.title, max_length=SOURCE_TITLE_MAX_LENGTH),
                "summary": source.summary,
                "author": _truncate_optional_text(source.author, max_length=SOURCE_AUTHOR_MAX_LENGTH),
                "image_url": _truncate_optional_text(source.image_url, max_length=SOURCE_IMAGE_URL_MAX_LENGTH),
            },
        )
        db.execute(
            text(
                """
                INSERT INTO rss_source_feeds (
                    source_id,
                    feed_id,
                    ingested_at
                ) VALUES (
                    :source_id,
                    :feed_id,
                    :ingested_at
                )
                ON CONFLICT (source_id, feed_id, ingested_at) DO NOTHING
                """
            ),
            {
                "source_id": int(upserted_source["id"]),
                "feed_id": operation.feed_id,
                "ingested_at": upserted_source["ingested_at"],
            },
        )


def _build_source_ingest_operations(
    payloads: list[WorkerResultSchema],
    *,
    feed_company_names: dict[int, str | None],
) -> list[_SourceIngestOperation]:
    operations: list[_SourceIngestOperation] = []
    for payload in payloads:
        feed_company_name = feed_company_names.get(payload.feed_id)
        for source in payload.sources:
            operations.append(
                _SourceIngestOperation(
                    source=source,
                    feed_id=payload.feed_id,
                    feed_company_name=feed_company_name,
                )
            )
    return sorted(
        operations,
        key=lambda operation: (
            *_source_upsert_lock_key(operation.source),
            operation.feed_id,
        ),
    )


def _normalize_published_at(published_at: datetime | None) -> datetime:
    if published_at is None:
        return SOURCE_PUBLISHED_AT_FALLBACK
    if published_at.tzinfo is None:
        return published_at.replace(tzinfo=timezone.utc)
    return published_at.astimezone(timezone.utc)


def _source_upsert_lock_key(source: WorkerSourceSchema) -> tuple[str, datetime, str]:
    return (
        source.url,
        _normalize_published_at(source.published_at),
        source.title,
    )


def _source_identity_key(url: str, published_at: datetime | None) -> tuple[str, datetime]:
    return (
        url,
        _normalize_published_at(published_at),
    )


def _list_feed_company_names(
    db: Session,
    *,
    feed_ids: list[int],
) -> dict[int, str | None]:
    unique_feed_ids = sorted({int(feed_id) for feed_id in feed_ids if int(feed_id) > 0})
    if not unique_feed_ids:
        return {}

    rows = db.execute(
        text(
            """
            SELECT
                feed.id AS feed_id,
                company.name AS company_name
            FROM rss_feeds AS feed
            LEFT JOIN rss_company AS company
                ON company.id = feed.company_id
            WHERE feed.id = ANY(:feed_ids)
            """
        ),
        {"feed_ids": unique_feed_ids},
    ).mappings().all()
    return {
        int(row["feed_id"]): (str(row["company_name"]) if row["company_name"] is not None else None)
        for row in rows
    }


def _resolve_or_create_source(
    db: Session,
    *,
    url: str,
    title: str,
    published_at: datetime | None,
    feed_company_name: str | None,
    existing_sources_by_identity: dict[tuple[str, datetime], dict[str, object]],
    title_company_cache: dict[tuple[str | None, str | None], dict[str, object] | None],
) -> dict[str, object]:
    identity_key = _source_identity_key(url, published_at)
    existing_source = existing_sources_by_identity.get(identity_key)
    if existing_source is not None:
        return existing_source

    normalized_title = normalize_article_identity_text(title)
    normalized_company_name = normalize_article_identity_text(feed_company_name)
    cache_key = (normalized_title, normalized_company_name)
    if cache_key in title_company_cache:
        existing_source = title_company_cache[cache_key]
    else:
        existing_source = _find_existing_source_by_title_and_company(
            db,
            title=title,
            feed_company_name=feed_company_name,
        )
        title_company_cache[cache_key] = existing_source
    if existing_source is not None:
        existing_sources_by_identity[identity_key] = existing_source
        return existing_source

    created_source = db.execute(
        text(
            """
            INSERT INTO rss_sources (
                url,
                published_at,
                ingested_at,
                created_at,
                updated_at
            ) VALUES (
                :url,
                :published_at,
                now(),
                now(),
                now()
            )
            ON CONFLICT (url, published_at) DO NOTHING
            RETURNING id, ingested_at
            """
        ),
        {
            "url": url,
            "published_at": identity_key[1],
        },
    ).mappings().one_or_none()
    if created_source is None:
        created_source = _find_existing_source_by_identity(
            db,
            url=url,
            published_at=identity_key[1],
        )
    if created_source is None:
        raise RuntimeError(f"Unable to resolve rss source identity for url={url!r}")

    existing_sources_by_identity[identity_key] = {
        "id": int(created_source["id"]),
        "ingested_at": created_source["ingested_at"],
    }
    return existing_sources_by_identity[identity_key]


def _list_existing_sources_by_identities(
    db: Session,
    *,
    identities: list[tuple[str, datetime]],
) -> dict[tuple[str, datetime], dict[str, object]]:
    normalized_urls = sorted({url for url, _published_at in identities if url})
    if not normalized_urls:
        return {}

    rows = db.execute(
        text(
            """
            SELECT
                url,
                published_at,
                id,
                ingested_at
            FROM rss_sources
            WHERE url = ANY(:urls)
            ORDER BY url ASC, published_at ASC, id ASC
            """
        ),
        {"urls": normalized_urls},
    ).mappings().all()
    return {
        _source_identity_key(str(row["url"]), row["published_at"]): {
            "id": int(row["id"]),
            "ingested_at": row["ingested_at"],
        }
        for row in rows
    }


def _find_existing_source_by_identity(
    db: Session,
    *,
    url: str,
    published_at: datetime,
) -> dict[str, object] | None:
    return db.execute(
        text(
            """
            SELECT id, ingested_at
            FROM rss_sources
            WHERE url = :url
                AND published_at = :published_at
            ORDER BY id ASC
            LIMIT 1
            """
        ),
        {
            "url": url,
            "published_at": published_at,
        },
    ).mappings().one_or_none()


def _find_existing_source_by_title_and_company(
    db: Session,
    *,
    title: str,
    feed_company_name: str | None,
) -> dict[str, object] | None:
    normalized_feed_company_name = normalize_article_identity_text(feed_company_name)
    normalized_title = normalize_article_identity_text(title)
    if normalized_feed_company_name is None or normalized_title is None:
        return None

    rows = db.execute(
        text(
            """
            SELECT
                source.id,
                source.ingested_at,
                company.name AS company_name,
                content.title AS title
            FROM rss_sources AS source
            JOIN rss_source_contents AS content
                ON content.source_id = source.id
                AND content.ingested_at = source.ingested_at
            LEFT JOIN rss_source_feeds AS source_feed
                ON source_feed.source_id = source.id
                AND source_feed.ingested_at = source.ingested_at
            LEFT JOIN rss_feeds AS feed
                ON feed.id = source_feed.feed_id
            LEFT JOIN rss_company AS company
                ON company.id = feed.company_id
            WHERE lower(content.title) = lower(:title)
            ORDER BY source.id ASC
            """
        ),
        {"title": title},
    ).mappings().all()

    for row in rows:
        if normalize_article_identity_text(row["title"]) != normalized_title:
            continue
        if normalize_article_identity_text(row["company_name"]) != normalized_feed_company_name:
            continue
        return {
            "id": int(row["id"]),
            "ingested_at": row["ingested_at"],
        }

    return None


def _truncate_required_text(value: str, *, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[:max_length]


def _truncate_optional_text(value: str | None, *, max_length: int) -> str | None:
    if value is None or len(value) <= max_length:
        return value
    return value[:max_length]
