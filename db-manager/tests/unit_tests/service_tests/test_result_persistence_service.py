from datetime import datetime, timezone
from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.services.result_persistence_service as result_persistence_service_module
from app.schemas.worker_result_schema import WorkerResultSchema


def _build_payload() -> WorkerResultSchema:
    return WorkerResultSchema(
        job_id="job-1",
        ingest=True,
        feed_id=10,
        feed_url="https://example.com/rss.xml",
        status="success",
        fetchprotection=2,
        new_etag="etag-1",
        new_last_update=datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc),
        sources=[],
    )


def test_persist_worker_result_returns_false_for_duplicate_result(monkeypatch) -> None:
    db = Mock(spec=Session)
    payload = _build_payload()

    insert_mock = Mock(return_value=False)
    upsert_feed_state_mock = Mock()
    upsert_sources_mock = Mock()
    refresh_job_mock = Mock()

    monkeypatch.setattr(result_persistence_service_module, "insert_job_result_if_new", insert_mock)
    monkeypatch.setattr(result_persistence_service_module, "upsert_feed_scraping_state", upsert_feed_state_mock)
    monkeypatch.setattr(result_persistence_service_module, "upsert_sources_for_feed", upsert_sources_mock)
    monkeypatch.setattr(result_persistence_service_module, "refresh_rss_scrape_job_status", refresh_job_mock)

    persisted = result_persistence_service_module.persist_worker_result(
        db,
        payload=payload,
        queue_kind="ingest",
    )

    assert persisted is False
    insert_mock.assert_called_once_with(
        db,
        payload=payload,
        queue_kind="ingest",
    )
    upsert_feed_state_mock.assert_not_called()
    upsert_sources_mock.assert_not_called()
    refresh_job_mock.assert_not_called()


def test_persist_worker_result_ingest_orchestrates_full_flow(monkeypatch) -> None:
    db = Mock(spec=Session)
    payload = _build_payload()

    insert_mock = Mock(return_value=True)
    upsert_feed_state_mock = Mock()
    upsert_sources_mock = Mock()
    refresh_job_mock = Mock()

    monkeypatch.setattr(result_persistence_service_module, "insert_job_result_if_new", insert_mock)
    monkeypatch.setattr(result_persistence_service_module, "upsert_feed_scraping_state", upsert_feed_state_mock)
    monkeypatch.setattr(result_persistence_service_module, "upsert_sources_for_feed", upsert_sources_mock)
    monkeypatch.setattr(result_persistence_service_module, "refresh_rss_scrape_job_status", refresh_job_mock)

    persisted = result_persistence_service_module.persist_worker_result(
        db,
        payload=payload,
        queue_kind="ingest",
    )

    assert persisted is True
    upsert_feed_state_mock.assert_called_once_with(db, payload=payload)
    upsert_sources_mock.assert_called_once_with(db, payload=payload)
    refresh_job_mock.assert_called_once_with(db, job_id="job-1")


def test_persist_worker_result_check_skips_source_ingest(monkeypatch) -> None:
    db = Mock(spec=Session)
    payload = _build_payload()

    monkeypatch.setattr(result_persistence_service_module, "insert_job_result_if_new", Mock(return_value=True))
    monkeypatch.setattr(result_persistence_service_module, "upsert_feed_scraping_state", Mock())
    upsert_sources_mock = Mock()
    monkeypatch.setattr(result_persistence_service_module, "upsert_sources_for_feed", upsert_sources_mock)
    monkeypatch.setattr(result_persistence_service_module, "refresh_rss_scrape_job_status", Mock())

    persisted = result_persistence_service_module.persist_worker_result(
        db,
        payload=payload,
        queue_kind="check",
    )

    assert persisted is True
    upsert_sources_mock.assert_not_called()
