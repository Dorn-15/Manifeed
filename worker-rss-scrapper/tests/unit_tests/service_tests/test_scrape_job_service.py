import asyncio
from unittest.mock import Mock

import app.services.scrape_job_service as scrape_job_service_module
from app.schemas.scrape_result_schema import ScrapeResultSchema


def test_process_job_message_acks_invalid_payload(monkeypatch) -> None:
    acked_messages: list[str] = []

    async def fake_ack_scrape_job(message_id: str) -> None:
        acked_messages.append(message_id)

    monkeypatch.setattr(scrape_job_service_module, "ack_scrape_job", fake_ack_scrape_job)

    asyncio.run(
        scrape_job_service_module._process_job_message(
            message_id="1-0",
            payload={"invalid": "payload"},
            http_client=Mock(),
            company_rate_limiters={},
            company_max_rps=4,
        )
    )

    assert acked_messages == ["1-0"]


def test_process_job_message_routes_check_and_error_results(monkeypatch) -> None:
    check_payloads: list[dict] = []
    error_payloads: list[dict] = []
    acked_messages: list[str] = []

    async def fake_fetch_feed_result(*, feed, ingest, http_client):
        if feed.feed_id == 1:
            return ScrapeResultSchema(
                job_id="",
                ingest=ingest,
                feed_id=feed.feed_id,
                feed_url=feed.feed_url,
                status="success",
                fetchprotection=feed.fetchprotection,
                sources=[],
            )
        return ScrapeResultSchema(
            job_id="",
            ingest=ingest,
            feed_id=feed.feed_id,
            feed_url=feed.feed_url,
            status="error",
            error_message="timeout",
            fetchprotection=feed.fetchprotection,
            sources=[],
        )

    async def fake_publish_check_result(payload: dict) -> None:
        check_payloads.append(payload)

    async def fake_publish_error_result(payload: dict) -> None:
        error_payloads.append(payload)

    async def fake_publish_ingest_result(payload: dict) -> None:
        raise AssertionError("publish_ingest_result must not be called for ingest=false")

    async def fake_ack_scrape_job(message_id: str) -> None:
        acked_messages.append(message_id)

    monkeypatch.setattr(scrape_job_service_module, "fetch_feed_result", fake_fetch_feed_result)
    monkeypatch.setattr(scrape_job_service_module, "publish_check_result", fake_publish_check_result)
    monkeypatch.setattr(scrape_job_service_module, "publish_error_result", fake_publish_error_result)
    monkeypatch.setattr(scrape_job_service_module, "publish_ingest_result", fake_publish_ingest_result)
    monkeypatch.setattr(scrape_job_service_module, "ack_scrape_job", fake_ack_scrape_job)

    payload = {
        "job_id": "job-1",
        "requested_at": "2026-02-26T12:00:00Z",
        "ingest": False,
        "requested_by": "rss_feeds_check_endpoint",
        "feeds": [
            {"feed_id": 1, "feed_url": "https://example.com/ok.xml", "fetchprotection": 1},
            {"feed_id": 2, "feed_url": "https://example.com/ko.xml", "fetchprotection": 1},
        ],
    }

    asyncio.run(
        scrape_job_service_module._process_job_message(
            message_id="2-0",
            payload=payload,
            http_client=Mock(),
            company_rate_limiters={},
            company_max_rps=4,
        )
    )

    assert len(check_payloads) == 1
    assert check_payloads[0]["feed_id"] == 1
    assert len(error_payloads) == 1
    assert error_payloads[0]["feed_id"] == 2
    assert acked_messages == ["2-0"]


def test_process_job_message_routes_ingest_results(monkeypatch) -> None:
    ingest_payloads: list[dict] = []

    async def fake_fetch_feed_result(*, feed, ingest, http_client):
        return ScrapeResultSchema(
            job_id="",
            ingest=ingest,
            feed_id=feed.feed_id,
            feed_url=feed.feed_url,
            status="success",
            fetchprotection=feed.fetchprotection,
            sources=[],
        )

    async def fake_publish_ingest_result(payload: dict) -> None:
        ingest_payloads.append(payload)

    async def fake_publish_check_result(payload: dict) -> None:
        raise AssertionError("publish_check_result must not be called for ingest=true")

    async def fake_publish_error_result(payload: dict) -> None:
        raise AssertionError("publish_error_result must not be called on success")

    async def fake_ack_scrape_job(message_id: str) -> None:
        return None

    monkeypatch.setattr(scrape_job_service_module, "fetch_feed_result", fake_fetch_feed_result)
    monkeypatch.setattr(scrape_job_service_module, "publish_ingest_result", fake_publish_ingest_result)
    monkeypatch.setattr(scrape_job_service_module, "publish_check_result", fake_publish_check_result)
    monkeypatch.setattr(scrape_job_service_module, "publish_error_result", fake_publish_error_result)
    monkeypatch.setattr(scrape_job_service_module, "ack_scrape_job", fake_ack_scrape_job)

    payload = {
        "job_id": "job-2",
        "requested_at": "2026-02-26T12:00:00Z",
        "ingest": True,
        "requested_by": "sources_ingest_endpoint",
        "feeds": [
            {"feed_id": 10, "feed_url": "https://example.com/ingest.xml", "fetchprotection": 2},
        ],
    }

    asyncio.run(
        scrape_job_service_module._process_job_message(
            message_id="3-0",
            payload=payload,
            http_client=Mock(),
            company_rate_limiters={},
            company_max_rps=4,
        )
    )

    assert len(ingest_payloads) == 1
    assert ingest_payloads[0]["job_id"] == "job-2"


def test_process_job_message_starts_one_flow_per_company(monkeypatch) -> None:
    called_company_flows: list[tuple[str, list[int]]] = []
    acked_messages: list[str] = []

    async def fake_process_company_feed_pool(
        *,
        scrape_job,
        feeds,
        company_key,
        http_client,
        company_rate_limiters,
        company_max_rps,
    ):
        called_company_flows.append((company_key, [feed.feed_id for feed in feeds]))

    async def fake_ack_scrape_job(message_id: str) -> None:
        acked_messages.append(message_id)

    monkeypatch.setattr(scrape_job_service_module, "_process_company_feed_pool", fake_process_company_feed_pool)
    monkeypatch.setattr(scrape_job_service_module, "ack_scrape_job", fake_ack_scrape_job)

    payload = {
        "job_id": "job-3",
        "requested_at": "2026-02-26T12:00:00Z",
        "ingest": False,
        "requested_by": "rss_feeds_check_endpoint",
        "feeds": [
            {
                "feed_id": 1,
                "feed_url": "https://example.com/company-1-a.xml",
                "company_id": 10,
                "fetchprotection": 1,
            },
            {
                "feed_id": 2,
                "feed_url": "https://example.com/company-1-b.xml",
                "company_id": 10,
                "fetchprotection": 1,
            },
            {
                "feed_id": 3,
                "feed_url": "https://example.com/company-2-a.xml",
                "company_id": 20,
                "fetchprotection": 1,
            },
        ],
    }

    asyncio.run(
        scrape_job_service_module._process_job_message(
            message_id="4-0",
            payload=payload,
            http_client=Mock(),
            company_rate_limiters={},
            company_max_rps=4,
        )
    )

    assert called_company_flows == [
        ("company:10", [1, 2]),
        ("company:20", [3]),
    ]
    assert acked_messages == ["4-0"]


def test_company_rate_limiter_schedules_release_after_one_second(monkeypatch) -> None:
    scheduled_delays: list[float] = []

    class FakeLoop:
        def call_later(self, delay: float, callback) -> None:
            scheduled_delays.append(delay)

    monkeypatch.setattr(scrape_job_service_module.asyncio, "get_running_loop", lambda: FakeLoop())
    limiter = scrape_job_service_module.CompanyRateLimiter(max_requests_per_second=2)

    async def run() -> None:
        await limiter.acquire()
        await limiter.acquire()

    asyncio.run(run())

    assert scheduled_delays == [1.0, 1.0]
