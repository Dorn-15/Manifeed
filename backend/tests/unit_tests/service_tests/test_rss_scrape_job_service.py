from datetime import datetime, timezone
from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.services.rss.rss_scrape_job_service as rss_scrape_job_service_module
from app.schemas.rss import RssScrapeFeedPayloadSchema, RssScrapeJobStatusRead


def test_enqueue_rss_feed_check_job_validates_local_payload(monkeypatch) -> None:
    db = Mock(spec=Session)
    requested_at = datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "list_rss_feed_scrape_payloads",
        lambda _db, *, feed_ids, enabled_only: [
            RssScrapeFeedPayloadSchema(feed_id=1, feed_url="https://example.com/a.xml", company_id=10),
            RssScrapeFeedPayloadSchema(feed_id=2, feed_url="https://example.com/b.xml", company_id=10),
        ],
    )
    create_calls = []
    enqueue_calls = []
    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "create_rss_scrape_job",
        lambda _db, **kwargs: create_calls.append(kwargs),
    )
    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "enqueue_rss_scrape_tasks",
        lambda _db, **kwargs: enqueue_calls.append(kwargs) or len(kwargs["feed_batches"]),
    )

    class _FakeDatetime:
        @staticmethod
        def now(tz=None):
            return requested_at

    monkeypatch.setattr(rss_scrape_job_service_module, "datetime", _FakeDatetime)

    result = rss_scrape_job_service_module.enqueue_rss_feed_check_job(
        db,
        feed_ids=[1, 2, 3],
    )

    assert create_calls[0]["requested_by"] == "rss_feeds_check_endpoint"
    assert [[feed.feed_id for feed in batch] for batch in enqueue_calls[0]["feed_batches"]] == [[1, 2]]
    assert result.job_kind == "rss_scrape_check"
    assert result.tasks_total == 1
    assert result.feeds_total == 2
    db.commit.assert_called_once()


def test_enqueue_rss_sources_ingest_job_validates_local_payload(monkeypatch) -> None:
    db = Mock(spec=Session)
    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "list_rss_feed_scrape_payloads",
        lambda _db, *, feed_ids, enabled_only: [],
    )
    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "create_rss_scrape_job",
        lambda _db, **kwargs: None,
    )
    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "enqueue_rss_scrape_tasks",
        lambda _db, **kwargs: 0,
    )

    result = rss_scrape_job_service_module.enqueue_rss_sources_ingest_job(
        db,
        feed_ids=[7, 8],
    )

    assert result.status == "completed"
    assert result.feeds_total == 0
    db.commit.assert_called_once()


def test_get_rss_scrape_job_status_validates_payload(monkeypatch) -> None:
    db = Mock(spec=Session)
    expected = RssScrapeJobStatusRead(
        job_id="job-1",
        ingest=False,
        requested_by="rss_feeds_check_endpoint",
        requested_at=datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc),
        status="processing",
        tasks_total=2,
        tasks_processed=1,
        feeds_total=2,
        feeds_processed=1,
        feeds_success=1,
        feeds_not_modified=0,
        feeds_error=0,
    )
    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "get_rss_scrape_job_status_read",
        lambda _db, *, job_id: expected if job_id == "job-1" else None,
    )

    result = rss_scrape_job_service_module.get_rss_scrape_job_status(db, job_id="job-1")

    assert result.job_id == "job-1"
    assert result.requested_at == datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)
    assert result.feeds_success == 1


def test_list_rss_scrape_job_feeds_validates_items(monkeypatch) -> None:
    db = Mock(spec=Session)
    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "get_rss_scrape_job_status_read",
        lambda _db, *, job_id: object() if job_id == "job-1" else None,
    )
    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "list_rss_scrape_job_feed_reads",
        lambda _db, *, job_id: [
            {
                "feed_id": 1,
                "feed_url": "https://example.com/a.xml",
                "status": "success",
            }
        ],
    )

    result = rss_scrape_job_service_module.list_rss_scrape_job_feeds(db, job_id="job-1")

    assert len(result) == 1
    assert result[0]["feed_id"] == 1
