from datetime import date
import importlib
from fastapi import HTTPException

from app.schemas.sources import (
    RssSourceEmbeddingMapPointRead,
    RssSourceEmbeddingMapRead,
)

sources_router_module = importlib.import_module("app.routers.sources_router")


def test_source_visualizer_endpoint_happy_path(client, monkeypatch) -> None:
    expected = RssSourceEmbeddingMapRead(
        items=[
            RssSourceEmbeddingMapPointRead(
                source_id=9,
                title="Source 9",
                url="https://example.com/9",
                company_names=["ACME"],
                x=0.11,
                y=-0.32,
            )
        ],
        total=1,
        date_from=date(2026, 2, 1),
        date_to=date(2026, 2, 28),
        embedding_model_name="intfloat/multilingual-e5-large",
        projection_version="ipca_umap_cosine_v3",
    )

    monkeypatch.setattr(
        sources_router_module,
        "get_rss_source_embedding_map",
        lambda db, *, date_from, date_to: expected,
    )

    response = client.get("/sources/visualizer?date_from=2026-02-01&date_to=2026-02-28")

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")


def test_source_visualizer_neighbors_endpoint_returns_404(client, monkeypatch) -> None:
    monkeypatch.setattr(
        sources_router_module,
        "get_rss_source_embedding_neighbors",
        lambda db, *, source_id, neighbor_limit, date_from, date_to: (_ for _ in ()).throw(
            HTTPException(status_code=404, detail=f"Source embedding projection {source_id} not found")
        ),
    )

    response = client.get("/sources/visualizer/999/neighbors?date_from=2026-02-01&date_to=2026-02-28")

    assert response.status_code == 404
    assert response.json() == {"detail": "Source embedding projection 999 not found"}
