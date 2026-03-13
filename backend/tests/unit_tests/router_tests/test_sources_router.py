import importlib
from contextlib import contextmanager
from datetime import date
from fastapi import HTTPException

from app.schemas.sources import (
    RssSourceEmbeddingEnqueueRead,
    RssSourceEmbeddingMapRead,
    RssSourceEmbeddingNeighborhoodRead,
    RssSourceEmbeddingNeighborRead,
    RssSourceEmbeddingMapPointRead,
    RssSourceDetailRead,
    RssSourcePartitionMaintenanceRead,
    RssSourcePageRead,
    RssSourceRead,
)
from app.utils import JobAlreadyRunning

sources_router_module = importlib.import_module("app.routers.sources_router")


@contextmanager
def _no_op_job_lock(_db, _name):
    yield


def test_read_sources_route_returns_service_payload(client, mock_db_session, monkeypatch) -> None:
    expected = RssSourcePageRead(
        items=[
            RssSourceRead(
                id=1,
                title="Article",
                url="https://example.com/a",
                company_names=["ACME"],
            )
        ],
        total=1,
        limit=50,
        offset=0,
    )

    def fake_get_rss_sources(db, *, limit, offset, feed_id=None, company_id=None):
        assert db is mock_db_session
        assert limit == 50
        assert offset == 0
        assert feed_id is None
        assert company_id is None
        return expected

    monkeypatch.setattr(sources_router_module, "get_rss_sources", fake_get_rss_sources)

    response = client.get("/sources/")

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")


def test_read_source_by_id_returns_404_when_not_found(client, mock_db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        sources_router_module,
        "get_rss_source_by_id",
        lambda db, *, source_id: (_ for _ in ()).throw(
            HTTPException(status_code=404, detail=f"RSS source {source_id} not found")
        ),
    )

    response = client.get("/sources/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "RSS source 999 not found"}


def test_ingest_sources_route_passes_feed_ids(client, mock_db_session, monkeypatch) -> None:
    def fake_enqueue_sources_ingest_job(db, *, feed_ids=None):
        assert db is mock_db_session
        assert feed_ids == [3, 4]
        return {
            "job_id": "job-456",
            "job_kind": "rss_scrape_ingest",
            "status": "queued",
            "tasks_total": 1,
            "feeds_total": 2,
        }

    monkeypatch.setattr(
        sources_router_module,
        "enqueue_sources_ingest_job",
        fake_enqueue_sources_ingest_job,
    )

    response = client.post("/sources/ingest?feed_ids=3&feed_ids=4")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": "job-456",
        "job_kind": "rss_scrape_ingest",
        "status": "queued",
        "tasks_total": 1,
        "feeds_total": 2,
    }


def test_enqueue_non_embedded_sources_route_returns_service_payload(
    client,
    mock_db_session,
    monkeypatch,
) -> None:
    def fake_enqueue_sources_without_embeddings(db, *, reembed_model_mismatches: bool):
        assert db is mock_db_session
        assert reembed_model_mismatches is False
        return RssSourceEmbeddingEnqueueRead(
            queued_sources=4,
        )

    monkeypatch.setattr(
        sources_router_module,
        "enqueue_sources_without_embeddings",
        fake_enqueue_sources_without_embeddings,
    )

    response = client.post("/sources/embeddings/enqueue")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": None,
        "job_kind": "source_embedding",
        "status": "queued",
        "tasks_total": 0,
        "items_total": 0,
        "queued_sources": 4,
    }


def test_enqueue_non_embedded_sources_route_supports_reembed_model_mismatches(
    client,
    mock_db_session,
    monkeypatch,
) -> None:
    def fake_enqueue_sources_without_embeddings(db, *, reembed_model_mismatches: bool):
        assert db is mock_db_session
        assert reembed_model_mismatches is True
        return RssSourceEmbeddingEnqueueRead(
            queued_sources=6,
        )

    monkeypatch.setattr(
        sources_router_module,
        "enqueue_sources_without_embeddings",
        fake_enqueue_sources_without_embeddings,
    )

    response = client.post("/sources/embeddings/enqueue?reembed_model_mismatches=true")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": None,
        "job_kind": "source_embedding",
        "status": "queued",
        "tasks_total": 0,
        "items_total": 0,
        "queued_sources": 6,
    }

def test_read_source_embedding_visualizer_route_returns_service_payload(
    client,
    mock_db_session,
    monkeypatch,
) -> None:
    expected = RssSourceEmbeddingMapRead(
        items=[
            RssSourceEmbeddingMapPointRead(
                source_id=18,
                title="Visualized source",
                summary="A summary",
                url="https://example.com/18",
                company_names=["ACME"],
                x=-0.22,
                y=0.91,
            )
        ],
        total=1,
        date_from=date(2026, 2, 1),
        date_to=date(2026, 2, 28),
        embedding_model_name="intfloat/multilingual-e5-large",
        projection_version="ipca_umap_cosine_v3",
    )

    def fake_get_rss_source_embedding_map(db, *, date_from, date_to):
        assert db is mock_db_session
        assert date_from == date(2026, 2, 1)
        assert date_to == date(2026, 2, 28)
        return expected

    monkeypatch.setattr(
        sources_router_module,
        "get_rss_source_embedding_map",
        fake_get_rss_source_embedding_map,
    )

    response = client.get("/sources/visualizer?date_from=2026-02-01&date_to=2026-02-28")

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")


def test_read_source_embedding_neighbors_route_returns_service_payload(
    client,
    mock_db_session,
    monkeypatch,
) -> None:
    expected = RssSourceEmbeddingNeighborhoodRead(
        source=RssSourceEmbeddingMapPointRead(
            source_id=18,
            title="Source 18",
            url="https://example.com/18",
            company_names=["ACME"],
            x=-0.22,
            y=0.91,
        ),
        neighbors=[
            RssSourceEmbeddingNeighborRead(
                source_id=22,
                title="Neighbor 22",
                url="https://example.com/22",
                company_names=["ACME"],
                x=-0.18,
                y=0.84,
                similarity=0.9912,
            )
        ],
        neighbor_limit=8,
        date_from=date(2026, 2, 1),
        date_to=date(2026, 2, 28),
        embedding_model_name="intfloat/multilingual-e5-large",
        projection_version="ipca_umap_cosine_v3",
    )

    def fake_get_rss_source_embedding_neighbors(
        db,
        *,
        source_id,
        neighbor_limit,
        date_from,
        date_to,
    ):
        assert db is mock_db_session
        assert source_id == 18
        assert neighbor_limit == 8
        assert date_from == date(2026, 2, 1)
        assert date_to == date(2026, 2, 28)
        return expected

    monkeypatch.setattr(
        sources_router_module,
        "get_rss_source_embedding_neighbors",
        fake_get_rss_source_embedding_neighbors,
    )

    response = client.get("/sources/visualizer/18/neighbors?date_from=2026-02-01&date_to=2026-02-28")

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")


def test_repartition_sources_default_route_returns_service_payload(
    client,
    mock_db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(sources_router_module, "job_lock", _no_op_job_lock)

    def fake_repartition_rss_source_partitions(db):
        assert db is mock_db_session
        return RssSourcePartitionMaintenanceRead(
            source_default_rows_repartitioned=5,
            source_feed_default_rows_repartitioned=7,
            source_weekly_partitions_created=2,
            source_feed_weekly_partitions_created=2,
            weeks_covered=2,
        )

    monkeypatch.setattr(
        sources_router_module,
        "repartition_rss_source_partitions",
        fake_repartition_rss_source_partitions,
    )

    response = client.post("/sources/partitions/repartition-default")

    assert response.status_code == 200
    assert response.json() == {
        "status": "completed",
        "source_default_rows_repartitioned": 5,
        "source_feed_default_rows_repartitioned": 7,
        "source_weekly_partitions_created": 2,
        "source_feed_weekly_partitions_created": 2,
        "weeks_covered": 2,
    }


def test_repartition_sources_default_route_returns_409_when_job_is_running(client, monkeypatch) -> None:
    @contextmanager
    def busy_job_lock(_db, _name):
        raise JobAlreadyRunning("sources_repartition_partitions")
        yield

    monkeypatch.setattr(sources_router_module, "job_lock", busy_job_lock)

    response = client.post("/sources/partitions/repartition-default")

    assert response.status_code == 409
    assert response.json() == {"message": "Sources partition repartition already running"}


def test_read_sources_route_returns_422_for_invalid_limit(client) -> None:
    response = client.get("/sources/?limit=1000")

    assert response.status_code == 422


def test_read_source_by_id_route_returns_payload(client, mock_db_session, monkeypatch) -> None:
    expected = RssSourceDetailRead(
        id=7,
        title="Source 7",
        url="https://example.com/s/7",
        company_names=["ACME"],
        feed_sections=["Main"],
    )

    def fake_get_rss_source_by_id(db, *, source_id):
        assert db is mock_db_session
        return expected if source_id == 7 else None

    monkeypatch.setattr(
        sources_router_module,
        "get_rss_source_by_id",
        fake_get_rss_source_by_id,
    )

    response = client.get("/sources/7")

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")
