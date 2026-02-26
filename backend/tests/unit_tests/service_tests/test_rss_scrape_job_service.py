import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock

from fastapi import HTTPException
import pytest
from sqlalchemy.orm import Session

from app.errors.rss import RssJobQueuePublishError
import app.services.rss.rss_scrape_job_service as rss_scrape_job_service_module
from app.schemas.rss import RssScrapeFeedPayloadSchema, RssScrapeJobStatusRead


def test_enqueue_rss_feed_check_job_publishes_message(monkeypatch) -> None:
    db = Mock(spec=Session)
    feeds = [
        RssScrapeFeedPayloadSchema(
            feed_id=1,
            feed_url="https://example.com/rss.xml",
            fetchprotection=1,
        )
    ]

    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "list_rss_feed_scrape_payloads",
        lambda _db, feed_ids=None, enabled_only=False: feeds,
    )

    created_jobs: list[dict] = []

    def fake_create_rss_scrape_job(
        _db,
        *,
        job_id,
        ingest,
        requested_by,
        requested_at,
        status,
        feeds,
    ):
        created_jobs.append(
            {
                "job_id": job_id,
                "ingest": ingest,
                "requested_by": requested_by,
                "requested_at": requested_at,
                "status": status,
                "feeds": feeds,
            }
        )
        return object()

    monkeypatch.setattr(rss_scrape_job_service_module, "create_rss_scrape_job", fake_create_rss_scrape_job)

    published_payloads: list[dict] = []

    async def fake_publish_rss_scrape_job(payload):
        published_payloads.append(payload)
        return "1-0"

    monkeypatch.setattr(rss_scrape_job_service_module, "publish_rss_scrape_job", fake_publish_rss_scrape_job)

    result = asyncio.run(rss_scrape_job_service_module.enqueue_rss_feed_check_job(db, feed_ids=[1]))

    assert result.status == "queued"
    assert len(created_jobs) == 1
    assert len(published_payloads) == 1
    assert published_payloads[0]["ingest"] is False
    assert published_payloads[0]["feeds"][0]["feed_id"] == 1
    db.commit.assert_called_once()


def test_enqueue_rss_feed_check_job_commits_before_publish(monkeypatch) -> None:
    db = Mock(spec=Session)
    feeds = [
        RssScrapeFeedPayloadSchema(
            feed_id=1,
            feed_url="https://example.com/rss.xml",
            fetchprotection=1,
        )
    ]

    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "list_rss_feed_scrape_payloads",
        lambda _db, feed_ids=None, enabled_only=False: feeds,
    )
    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "create_rss_scrape_job",
        lambda *args, **kwargs: object(),
    )

    async def fake_publish_rss_scrape_job(payload):
        assert db.commit.call_count == 1
        return "1-0"

    monkeypatch.setattr(rss_scrape_job_service_module, "publish_rss_scrape_job", fake_publish_rss_scrape_job)

    asyncio.run(rss_scrape_job_service_module.enqueue_rss_feed_check_job(db, feed_ids=[1]))

    assert db.commit.call_count == 1


def test_enqueue_rss_feed_check_job_marks_failed_if_publish_fails(monkeypatch) -> None:
    db = Mock(spec=Session)
    feeds = [
        RssScrapeFeedPayloadSchema(
            feed_id=1,
            feed_url="https://example.com/rss.xml",
            fetchprotection=1,
        )
    ]

    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "list_rss_feed_scrape_payloads",
        lambda _db, feed_ids=None, enabled_only=False: feeds,
    )
    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "create_rss_scrape_job",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "set_rss_scrape_job_status",
        lambda _db, *, job_id, status: status == "failed",
    )

    async def fake_publish_rss_scrape_job(payload):
        raise RuntimeError("redis down")

    monkeypatch.setattr(rss_scrape_job_service_module, "publish_rss_scrape_job", fake_publish_rss_scrape_job)

    with pytest.raises(RssJobQueuePublishError):
        asyncio.run(rss_scrape_job_service_module.enqueue_rss_feed_check_job(db, feed_ids=[1]))

    assert db.commit.call_count == 2


def test_get_rss_scrape_job_status_raises_404_when_missing(monkeypatch) -> None:
    db = Mock(spec=Session)
    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "get_rss_scrape_job_status_read",
        lambda _db, job_id: None,
    )

    with pytest.raises(HTTPException) as exception_info:
        rss_scrape_job_service_module.get_rss_scrape_job_status(db, job_id="missing")

    assert exception_info.value.status_code == 404


def test_get_rss_scrape_job_status_returns_payload(monkeypatch) -> None:
    db = Mock(spec=Session)
    expected = RssScrapeJobStatusRead(
        job_id="job-1",
        ingest=False,
        requested_by="rss_feeds_check_endpoint",
        requested_at=datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc),
        status="processing",
        feeds_total=2,
        feeds_processed=1,
        feeds_success=1,
        feeds_not_modified=0,
        feeds_error=0,
    )
    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "get_rss_scrape_job_status_read",
        lambda _db, job_id: expected,
    )

    result = rss_scrape_job_service_module.get_rss_scrape_job_status(db, job_id="job-1")

    assert result == expected


def test_mix_feeds_by_company_round_robin() -> None:
    feeds = [
        RssScrapeFeedPayloadSchema(
            feed_id=1,
            feed_url="https://example.com/a1.xml",
            company_id=10,
            fetchprotection=1,
        ),
        RssScrapeFeedPayloadSchema(
            feed_id=2,
            feed_url="https://example.com/a2.xml",
            company_id=10,
            fetchprotection=1,
        ),
        RssScrapeFeedPayloadSchema(
            feed_id=3,
            feed_url="https://example.com/b1.xml",
            company_id=20,
            fetchprotection=1,
        ),
        RssScrapeFeedPayloadSchema(
            feed_id=4,
            feed_url="https://example.com/b2.xml",
            company_id=20,
            fetchprotection=1,
        ),
        RssScrapeFeedPayloadSchema(
            feed_id=5,
            feed_url="https://example.com/c1.xml",
            company_id=30,
            fetchprotection=1,
        ),
    ]

    mixed = rss_scrape_job_service_module._mix_feeds_by_company(feeds)

    assert [feed.feed_id for feed in mixed] == [1, 3, 5, 2, 4]


def test_enqueue_rss_feed_check_job_batches_and_mixes_company_feeds(monkeypatch) -> None:
    db = Mock(spec=Session)
    feeds = [
        RssScrapeFeedPayloadSchema(
            feed_id=1,
            feed_url="https://example.com/a1.xml",
            company_id=10,
            fetchprotection=1,
        ),
        RssScrapeFeedPayloadSchema(
            feed_id=2,
            feed_url="https://example.com/a2.xml",
            company_id=10,
            fetchprotection=1,
        ),
        RssScrapeFeedPayloadSchema(
            feed_id=3,
            feed_url="https://example.com/b1.xml",
            company_id=20,
            fetchprotection=1,
        ),
        RssScrapeFeedPayloadSchema(
            feed_id=4,
            feed_url="https://example.com/b2.xml",
            company_id=20,
            fetchprotection=1,
        ),
        RssScrapeFeedPayloadSchema(
            feed_id=5,
            feed_url="https://example.com/c1.xml",
            company_id=30,
            fetchprotection=1,
        ),
    ]

    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "list_rss_feed_scrape_payloads",
        lambda _db, feed_ids=None, enabled_only=False: feeds,
    )
    monkeypatch.setattr(
        rss_scrape_job_service_module,
        "create_rss_scrape_job",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setenv("RSS_SCRAPE_QUEUE_BATCH_SIZE", "2")

    published_payloads: list[dict] = []

    async def fake_publish_rss_scrape_job(payload):
        published_payloads.append(payload)
        return "1-0"

    monkeypatch.setattr(rss_scrape_job_service_module, "publish_rss_scrape_job", fake_publish_rss_scrape_job)

    asyncio.run(rss_scrape_job_service_module.enqueue_rss_feed_check_job(db, feed_ids=[1, 2, 3, 4, 5]))

    assert len(published_payloads) == 3
    assert [[feed["feed_id"] for feed in payload["feeds"]] for payload in published_payloads] == [
        [1, 3],
        [5, 2],
        [4],
    ]
