from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.clients.database import (
    get_rss_source_embedding_similarity_candidate,
    list_rss_source_embedding_map_points,
    list_rss_source_embedding_neighbors,
)
from app.schemas.sources import (
    RssSourceEmbeddingMapPointRead,
    RssSourceEmbeddingMapRead,
    RssSourceEmbeddingNeighborhoodRead,
    RssSourceEmbeddingNeighborRead,
    RssSourceEmbeddingSimilarityCandidateSchema,
)
from app.utils import resolve_embedding_model_name


DEFAULT_PROJECTION_VERSION = "ipca_umap_cosine_v3"


def get_rss_source_embedding_map(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
) -> RssSourceEmbeddingMapRead:
    embedding_model_name = _resolve_embedding_model_name()
    published_from, published_to_exclusive = _resolve_date_bounds(
        date_from=date_from,
        date_to=date_to,
    )
    items, total, projection_version = list_rss_source_embedding_map_points(
        db,
        model_name=embedding_model_name,
        published_from=published_from,
        published_to_exclusive=published_to_exclusive,
    )
    return RssSourceEmbeddingMapRead(
        items=items,
        total=total,
        date_from=date_from,
        date_to=date_to,
        embedding_model_name=embedding_model_name,
        projection_version=projection_version or DEFAULT_PROJECTION_VERSION,
    )


def get_rss_source_embedding_neighbors(
    db: Session,
    *,
    source_id: int,
    neighbor_limit: int,
    date_from: date | None,
    date_to: date | None,
) -> RssSourceEmbeddingNeighborhoodRead:
    embedding_model_name = _resolve_embedding_model_name()
    published_from, published_to_exclusive = _resolve_date_bounds(
        date_from=date_from,
        date_to=date_to,
    )
    source_candidate = get_rss_source_embedding_similarity_candidate(
        db,
        source_id=source_id,
        model_name=embedding_model_name,
        published_from=published_from,
        published_to_exclusive=published_to_exclusive,
    )
    if source_candidate is None:
        raise HTTPException(status_code=404, detail=f"Source embedding projection {source_id} not found")

    candidates = list_rss_source_embedding_neighbors(
        db,
        source_id=source_id,
        neighbor_limit=neighbor_limit,
        model_name=embedding_model_name,
        published_from=published_from,
        published_to_exclusive=published_to_exclusive,
    )
    return RssSourceEmbeddingNeighborhoodRead(
        source=_to_map_point_read(source_candidate),
        neighbors=[
            RssSourceEmbeddingNeighborRead(
                **_to_map_point_read(candidate).model_dump(),
                similarity=round(candidate.similarity or 0.0, 6),
            )
            for candidate in candidates
        ],
        neighbor_limit=neighbor_limit,
        date_from=date_from,
        date_to=date_to,
        embedding_model_name=embedding_model_name,
        projection_version=source_candidate.projection_version,
    )


def _resolve_embedding_model_name() -> str:
    return resolve_embedding_model_name()


def _resolve_date_bounds(
    *,
    date_from: date | None,
    date_to: date | None,
) -> tuple[datetime | None, datetime | None]:
    published_from = None
    if date_from is not None:
        published_from = datetime.combine(date_from, time.min, tzinfo=timezone.utc)

    published_to_exclusive = None
    if date_to is not None:
        published_to_exclusive = datetime.combine(
            date_to + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )

    return published_from, published_to_exclusive


def _to_map_point_read(
    candidate: RssSourceEmbeddingSimilarityCandidateSchema,
) -> RssSourceEmbeddingMapPointRead:
    return RssSourceEmbeddingMapPointRead(
        source_id=candidate.source_id,
        title=candidate.title,
        summary=candidate.summary,
        url=candidate.url,
        published_at=candidate.published_at,
        image_url=candidate.image_url,
        company_names=candidate.company_names,
        x=candidate.x,
        y=candidate.y,
    )
