import importlib
from contextlib import contextmanager
from fastapi import HTTPException

from app.schemas.sources import (
    RssSourceDetailRead,
    RssSourceIngestRead,
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

    def fake_get_rss_sources(db, limit, offset, feed_id=None, company_id=None):
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
        lambda db, source_id: (_ for _ in ()).throw(
            HTTPException(status_code=404, detail=f"RSS source {source_id} not found")
        ),
    )

    response = client.get("/sources/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "RSS source 999 not found"}


def test_ingest_sources_route_passes_feed_ids(client, mock_db_session, monkeypatch) -> None:
    monkeypatch.setattr(sources_router_module, "job_lock", _no_op_job_lock)

    async def fake_ingest_rss_sources(db, feed_ids=None):
        assert db is mock_db_session
        assert feed_ids == [3, 4]
        return RssSourceIngestRead(
            feeds_processed=1,
            feeds_skipped=0,
            sources_created=2,
            sources_updated=1,
            duration_ms=10,
        )

    monkeypatch.setattr(sources_router_module, "ingest_rss_sources", fake_ingest_rss_sources)

    response = client.post("/sources/ingest?feed_ids=3&feed_ids=4")

    assert response.status_code == 200
    assert response.json()["feeds_processed"] == 1


def test_ingest_sources_route_returns_409_when_job_is_running(client, monkeypatch) -> None:
    @contextmanager
    def busy_job_lock(_db, _name):
        raise JobAlreadyRunning("sources_ingest")
        yield

    monkeypatch.setattr(sources_router_module, "job_lock", busy_job_lock)

    response = client.post("/sources/ingest")

    assert response.status_code == 409
    assert response.json() == {"message": "Sources ingest already running"}


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

    monkeypatch.setattr(
        sources_router_module,
        "get_rss_source_by_id",
        lambda db, source_id: expected if source_id == 7 else None,
    )

    response = client.get("/sources/7")

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")
