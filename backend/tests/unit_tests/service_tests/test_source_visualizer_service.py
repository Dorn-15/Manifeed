from datetime import date
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

import app.services.sources.source_visualizer_service as source_visualizer_service_module
from app.schemas.sources import (
    RssSourceEmbeddingMapPointRead,
    RssSourceEmbeddingMapRead,
    RssSourceEmbeddingSimilarityCandidateSchema,
)


def _candidate(
    *,
    source_id: int,
    title: str,
    embedding: list[float],
    x: float,
    y: float,
) -> RssSourceEmbeddingSimilarityCandidateSchema:
    return RssSourceEmbeddingSimilarityCandidateSchema(
        source_id=source_id,
        title=title,
        url=f"https://example.com/{source_id}",
        company_names=["ACME"],
        x=x,
        y=y,
        embedding=embedding,
        embedding_model_name="intfloat/multilingual-e5-large",
        projection_version="ipca_umap_cosine_v3",
    )


def test_get_rss_source_embedding_map_returns_date_filtered_payload(monkeypatch) -> None:
    db = Mock(spec=Session)
    expected_items = [
        RssSourceEmbeddingMapPointRead(
            source_id=18,
            title="Source 18",
            url="https://example.com/18",
            company_names=["ACME"],
            x=0.14,
            y=-0.4,
        )
    ]

    monkeypatch.setattr(
        source_visualizer_service_module,
        "_resolve_embedding_model_name",
        lambda: "intfloat/multilingual-e5-large",
    )
    monkeypatch.setattr(
        source_visualizer_service_module,
        "list_rss_source_embedding_map_points",
        lambda _db, *, model_name, published_from, published_to_exclusive: (
            expected_items,
            45,
            "ipca_umap_cosine_v3",
        ),
    )

    result = source_visualizer_service_module.get_rss_source_embedding_map(
        db,
        date_from=date(2026, 2, 1),
        date_to=date(2026, 2, 28),
    )

    assert result == RssSourceEmbeddingMapRead(
        items=expected_items,
        total=45,
        date_from=date(2026, 2, 1),
        date_to=date(2026, 2, 28),
        embedding_model_name="intfloat/multilingual-e5-large",
        projection_version="ipca_umap_cosine_v3",
    )


def test_get_rss_source_embedding_neighbors_ranks_candidates(monkeypatch) -> None:
    db = Mock(spec=Session)
    anchor = _candidate(
        source_id=18,
        title="Anchor",
        embedding=[1.0, 0.0, 0.0],
        x=0.1,
        y=0.2,
    )
    near = _candidate(
        source_id=19,
        title="Near",
        embedding=[0.99, 0.01, 0.0],
        x=0.11,
        y=0.19,
    )
    far = _candidate(
        source_id=20,
        title="Far",
        embedding=[0.0, 1.0, 0.0],
        x=-0.8,
        y=0.7,
    )

    monkeypatch.setattr(
        source_visualizer_service_module,
        "_resolve_embedding_model_name",
        lambda: "intfloat/multilingual-e5-large",
    )
    monkeypatch.setattr(
        source_visualizer_service_module,
        "get_rss_source_embedding_similarity_candidate",
        lambda _db, *, source_id, model_name, published_from, published_to_exclusive: anchor if source_id == 18 else None,
    )
    monkeypatch.setattr(
        source_visualizer_service_module,
        "list_rss_source_embedding_neighbors",
        lambda _db, *, source_id, neighbor_limit, model_name, published_from, published_to_exclusive: [
            near.model_copy(update={"similarity": 0.99}),
            far.model_copy(update={"similarity": 0.0}),
        ],
    )

    result = source_visualizer_service_module.get_rss_source_embedding_neighbors(
        db,
        source_id=18,
        neighbor_limit=2,
        date_from=date(2026, 2, 1),
        date_to=date(2026, 2, 28),
    )

    assert result.source.source_id == 18
    assert [neighbor.source_id for neighbor in result.neighbors] == [19, 20]
    assert result.neighbors[0].similarity > result.neighbors[1].similarity


def test_get_rss_source_embedding_neighbors_raises_404_when_source_is_missing(monkeypatch) -> None:
    db = Mock(spec=Session)

    monkeypatch.setattr(
        source_visualizer_service_module,
        "_resolve_embedding_model_name",
        lambda: "intfloat/multilingual-e5-large",
    )
    monkeypatch.setattr(
        source_visualizer_service_module,
        "get_rss_source_embedding_similarity_candidate",
        lambda _db, *, source_id, model_name, published_from, published_to_exclusive: None,
    )

    with pytest.raises(HTTPException) as captured:
        source_visualizer_service_module.get_rss_source_embedding_neighbors(
            db,
            source_id=404,
            neighbor_limit=8,
            date_from=date(2026, 2, 1),
            date_to=date(2026, 2, 28),
        )

    assert captured.value.status_code == 404
    assert captured.value.detail == "Source embedding projection 404 not found"
