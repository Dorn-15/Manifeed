from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas import WorkerResultSchema

SOURCE_PUBLISHED_AT_FALLBACK = datetime(1970, 1, 1, tzinfo=timezone.utc)


def upsert_sources_for_feed(
    db: Session,
    *,
    payload: WorkerResultSchema,
) -> None:
    if payload.status != "success":
        return

    for source in payload.sources:
        published_at = _normalize_published_at(source.published_at)
        upserted_source = db.execute(
            text(
                """
                INSERT INTO rss_sources (
                    title,
                    summary,
                    author,
                    url,
                    published_at,
                    image_url
                ) VALUES (
                    :title,
                    :summary,
                    :author,
                    :url,
                    :published_at,
                    :image_url
                )
                ON CONFLICT (url, published_at) DO UPDATE SET
                    title = EXCLUDED.title,
                    summary = COALESCE(EXCLUDED.summary, rss_sources.summary),
                    author = COALESCE(EXCLUDED.author, rss_sources.author),
                    image_url = COALESCE(EXCLUDED.image_url, rss_sources.image_url)
                RETURNING id, published_at
                """
            ),
            {
                "title": source.title,
                "summary": source.summary,
                "author": source.author,
                "url": source.url,
                "published_at": published_at,
                "image_url": source.image_url,
            },
        ).mappings().first()
        if upserted_source is None:
            continue

        db.execute(
            text(
                """
                INSERT INTO rss_source_feeds (source_id, feed_id, published_at)
                VALUES (:source_id, :feed_id, :published_at)
                ON CONFLICT (source_id, feed_id, published_at) DO NOTHING
                """
            ),
            {
                "source_id": upserted_source["id"],
                "feed_id": payload.feed_id,
                "published_at": upserted_source["published_at"],
            },
        )


def _normalize_published_at(published_at: datetime | None) -> datetime:
    if published_at is None:
        return SOURCE_PUBLISHED_AT_FALLBACK
    if published_at.tzinfo is None:
        return published_at.replace(tzinfo=timezone.utc)
    return published_at.astimezone(timezone.utc)
