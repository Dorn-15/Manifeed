import importlib

from app.schemas.rss import (
    RssScrapeJobFeedRead,
    RssScrapeJobStatusRead,
)

jobs_router_module = importlib.import_module("app.routers.jobs_router")


def test_read_job_status_returns_service_payload(client, mock_db_session, monkeypatch) -> None:
    expected = RssScrapeJobStatusRead(
        job_id="job-1",
        ingest=False,
        requested_by="rss_feeds_check_endpoint",
        requested_at="2026-02-26T12:00:00Z",
        status="queued",
        feeds_total=2,
        feeds_processed=0,
        feeds_success=0,
        feeds_not_modified=0,
        feeds_error=0,
    )

    def fake_get_rss_scrape_job_status(db, job_id):
        assert db is mock_db_session
        assert job_id == "job-1"
        return expected

    monkeypatch.setattr(jobs_router_module, "get_rss_scrape_job_status", fake_get_rss_scrape_job_status)

    response = client.get("/jobs/job-1")

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")


def test_read_job_feeds_returns_service_payload(client, mock_db_session, monkeypatch) -> None:
    expected = [
        RssScrapeJobFeedRead(
            feed_id=1,
            feed_url="https://example.com/rss.xml",
            status="pending",
        )
    ]

    def fake_list_rss_scrape_job_feeds(db, job_id):
        assert db is mock_db_session
        assert job_id == "job-1"
        return expected

    monkeypatch.setattr(jobs_router_module, "list_rss_scrape_job_feeds", fake_list_rss_scrape_job_feeds)

    response = client.get("/jobs/job-1/feeds")

    assert response.status_code == 200
    assert response.json() == [item.model_dump(mode="json") for item in expected]
