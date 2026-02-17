import importlib
from contextlib import contextmanager

from app.schemas.sources import (
    RssSourceDetailRead,
    RssSourceIngestRead,
    RssSourcePageRead,
    RssSourceRead,
)
from app.utils import JobAlreadyRunning

sources_router_module = importlib.import_module("app.routers.sources_router")


def test_get_sources_route_returns_service_result(client, mock_db_session, monkeypatch) -> None:
    expected_response = RssSourcePageRead(
        items=[
            RssSourceRead(
                id=42,
                title="Source article",
                summary="Summary",
                url="https://example.com/article",
                image_url="https://example.com/img.jpg",
                company_name="The Verge",
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
        return expected_response

    monkeypatch.setattr(sources_router_module, "get_rss_sources", fake_get_rss_sources)

    response = client.get("/sources/")

    assert response.status_code == 200
    assert response.json() == expected_response.model_dump(mode="json")


def test_get_sources_by_feed_route_returns_service_result(
    client,
    mock_db_session,
    monkeypatch,
) -> None:
    expected_response = RssSourcePageRead(total=0, limit=6, offset=12)

    def fake_get_rss_sources(db, limit, offset, feed_id=None, company_id=None):
        assert db is mock_db_session
        assert feed_id == 9
        assert company_id is None
        assert limit == 6
        assert offset == 12
        return expected_response

    monkeypatch.setattr(
        sources_router_module,
        "get_rss_sources",
        fake_get_rss_sources,
    )

    response = client.get("/sources/feeds/9?limit=6&offset=12")

    assert response.status_code == 200
    assert response.json() == expected_response.model_dump(mode="json")


def test_get_sources_by_company_route_returns_service_result(
    client,
    mock_db_session,
    monkeypatch,
) -> None:
    expected_response = RssSourcePageRead(total=0, limit=20, offset=0)

    def fake_get_rss_sources(db, limit, offset, feed_id=None, company_id=None):
        assert db is mock_db_session
        assert company_id == 3
        assert feed_id is None
        assert limit == 20
        assert offset == 0
        return expected_response

    monkeypatch.setattr(
        sources_router_module,
        "get_rss_sources",
        fake_get_rss_sources,
    )

    response = client.get("/sources/companies/3?limit=20")

    assert response.status_code == 200
    assert response.json() == expected_response.model_dump(mode="json")


def test_get_source_by_id_route_returns_service_result(client, mock_db_session, monkeypatch) -> None:
    expected_response = RssSourceDetailRead(
        id=7,
        title="Source 7",
        summary="Summary 7",
        url="https://example.com/source-7",
        image_url=None,
        company_name="Wired",
        feed_sections=["AI", "Main"],
    )

    def fake_get_rss_source_by_id(db, source_id):
        assert db is mock_db_session
        assert source_id == 7
        return expected_response

    monkeypatch.setattr(sources_router_module, "get_rss_source_by_id", fake_get_rss_source_by_id)

    response = client.get("/sources/7")

    assert response.status_code == 200
    assert response.json() == expected_response.model_dump(mode="json")


def test_get_source_by_id_route_returns_404_when_missing(
    client,
    mock_db_session,
    monkeypatch,
) -> None:
    def fake_get_rss_source_by_id(db, source_id):
        assert db is mock_db_session
        assert source_id == 700
        return None

    monkeypatch.setattr(sources_router_module, "get_rss_source_by_id", fake_get_rss_source_by_id)

    response = client.get("/sources/700")

    assert response.status_code == 404
    assert response.json() == {"detail": "RSS source 700 not found"}


def test_ingest_sources_route_returns_service_result(
    client,
    mock_db_session,
    monkeypatch,
) -> None:
    expected_response = RssSourceIngestRead(
        status="completed",
        feeds_processed=2,
        feeds_skipped=1,
        sources_created=4,
        sources_updated=3,
        duration_ms=120,
    )

    async def fake_ingest_rss_sources(db, feed_ids):
        assert db is mock_db_session
        assert feed_ids == [3, 4]
        return expected_response

    monkeypatch.setattr(sources_router_module, "ingest_rss_sources", fake_ingest_rss_sources)

    response = client.post("/sources/ingest", json={"feed_ids": [3, 4]})

    assert response.status_code == 200
    assert response.json() == expected_response.model_dump()


def test_ingest_sources_route_returns_409_when_job_lock_is_busy(client, monkeypatch) -> None:
    @contextmanager
    def busy_job_lock(_db, _name):
        raise JobAlreadyRunning("sources_ingest")
        yield

    monkeypatch.setattr(sources_router_module, "job_lock", busy_job_lock)

    response = client.post("/sources/ingest")

    assert response.status_code == 409
    assert response.json() == {"message": "Sources ingest already running"}
