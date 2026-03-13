from datetime import datetime, timezone
from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.clients.database.rss_scraping_db_client as rss_scraping_db_client_module
from app.schemas import WorkerResultSchema


def _build_worker_result(*, resolved_fetchprotection: int | None) -> WorkerResultSchema:
    return WorkerResultSchema(
        job_id="job-1",
        ingest=False,
        feed_id=11,
        feed_url="https://example.com/feed.xml",
        status="success",
        new_etag="etag-1",
        new_last_update=datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc),
        fetchprotection=2,
        resolved_fetchprotection=resolved_fetchprotection,
        sources=[
            {
                "title": "Article",
                "url": "https://example.com/article",
                "published_at": datetime(2026, 3, 10, 14, 0, tzinfo=timezone.utc),
            }
        ],
    )


def test_upsert_feed_scraping_state_skips_fetchprotection_override_without_resolution() -> None:
    db = Mock(spec=Session)

    rss_scraping_db_client_module.upsert_feed_scraping_state(
        db,
        payload=_build_worker_result(resolved_fetchprotection=None),
        apply_resolved_fetchprotection=True,
    )

    assert db.execute.call_count == 1
    _, insert_params = db.execute.call_args_list[0].args
    assert insert_params["last_db_article_published_at"] == datetime(
        2026,
        3,
        10,
        14,
        0,
        tzinfo=timezone.utc,
    )


def test_upsert_feed_scraping_state_updates_fetchprotection_override_with_resolved_value() -> None:
    db = Mock(spec=Session)

    rss_scraping_db_client_module.upsert_feed_scraping_state(
        db,
        payload=_build_worker_result(resolved_fetchprotection=0),
        apply_resolved_fetchprotection=True,
    )

    assert db.execute.call_count == 3
    _, second_params = db.execute.call_args_list[1].args
    _, third_params = db.execute.call_args_list[2].args
    assert second_params == {"feed_id": 11, "fetchprotection": 0}
    assert third_params == {"feed_id": 11, "fetchprotection": 0}


def test_increment_rss_scrape_job_status_casts_case_to_worker_job_status_enum() -> None:
    db = Mock(spec=Session)

    rss_scraping_db_client_module.increment_rss_scrape_job_status(
        db,
        job_id="job-1",
        tasks_processed_delta=1,
        items_processed_delta=20,
        items_success_delta=20,
        items_error_delta=0,
    )

    query, params = db.execute.call_args.args
    sql = query.text if hasattr(query, "text") else str(query)
    assert "AS worker_job_status_enum" in sql
    assert "CASE" in sql
    assert params["job_id"] == "job-1"


def test_refresh_rss_scrape_job_status_casts_status_to_worker_job_status_enum() -> None:
    db = Mock(spec=Session)
    select_result = Mock()
    select_result.mappings.return_value.one_or_none.return_value = {
        "tasks_total": 1,
        "tasks_processed": 1,
        "items_total": 2,
        "items_processed": 2,
        "items_success": 2,
        "items_error": 0,
        "processing_count": 0,
        "pending_count": 0,
        "failed_task_count": 0,
    }
    db.execute.side_effect = [select_result, Mock()]

    rss_scraping_db_client_module.refresh_rss_scrape_job_status(db, job_id="job-1")

    query, params = db.execute.call_args_list[1].args
    sql = query.text if hasattr(query, "text") else str(query)
    assert "CAST(:status AS worker_job_status_enum)" in sql
    assert params["status"] == "completed"
