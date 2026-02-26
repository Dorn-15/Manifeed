from datetime import datetime, timezone
from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.clients.database.rss_scraping_db_client as rss_scraping_db_client_module
from app.schemas.worker_result_schema import WorkerResultSchema


def _build_payload(*, status: str = "success") -> WorkerResultSchema:
    return WorkerResultSchema(
        job_id="job-1",
        ingest=False,
        feed_id=5,
        feed_url="https://example.com/rss.xml",
        status=status,
        error_message="failed" if status == "error" else None,
        fetchprotection=2,
        new_etag="etag-1",
        new_last_update=datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc),
        sources=[],
    )


def test_insert_job_result_if_new_returns_true_when_inserted() -> None:
    db = Mock(spec=Session)
    db.execute.return_value.scalar_one_or_none.return_value = "job-1"

    inserted = rss_scraping_db_client_module.insert_job_result_if_new(
        db,
        payload=_build_payload(),
        queue_kind="check",
    )

    assert inserted is True
    db.execute.assert_called_once()


def test_insert_job_result_if_new_returns_false_when_conflict() -> None:
    db = Mock(spec=Session)
    db.execute.return_value.scalar_one_or_none.return_value = None

    inserted = rss_scraping_db_client_module.insert_job_result_if_new(
        db,
        payload=_build_payload(),
        queue_kind="check",
    )

    assert inserted is False


def test_insert_job_result_if_new_query_is_guarded_by_parent_job_existence() -> None:
    db = Mock(spec=Session)
    db.execute.return_value.scalar_one_or_none.return_value = None

    rss_scraping_db_client_module.insert_job_result_if_new(
        db,
        payload=_build_payload(),
        queue_kind="check",
    )

    sql_text = str(db.execute.call_args.args[0])
    assert "WHERE EXISTS" in sql_text
    assert "FROM rss_scrape_jobs" in sql_text


def test_upsert_feed_scraping_state_sets_error_flags() -> None:
    db = Mock(spec=Session)
    payload = _build_payload(status="error")

    rss_scraping_db_client_module.upsert_feed_scraping_state(db, payload=payload)

    params = db.execute.call_args.args[1]
    assert params["is_error"] is True
    assert params["error_nbr"] == 1
    assert params["error_msg"] == "failed"


def test_upsert_feed_scraping_state_clears_error_message_on_success() -> None:
    db = Mock(spec=Session)
    payload = _build_payload(status="success")

    rss_scraping_db_client_module.upsert_feed_scraping_state(db, payload=payload)

    params = db.execute.call_args.args[1]
    assert params["is_error"] is False
    assert params["error_nbr"] == 0
    assert params["error_msg"] is None


def test_refresh_rss_scrape_job_status_returns_when_job_does_not_exist() -> None:
    db = Mock(spec=Session)
    first_execute = Mock()
    first_execute.mappings.return_value.first.return_value = None
    db.execute.side_effect = [first_execute]

    rss_scraping_db_client_module.refresh_rss_scrape_job_status(db, job_id="missing-job")

    assert db.execute.call_count == 1


def test_refresh_rss_scrape_job_status_sets_completed_with_errors() -> None:
    db = Mock(spec=Session)

    job_row_result = Mock()
    job_row_result.mappings.return_value.first.return_value = {"feed_count": 2}

    counts_result = Mock()
    counts_result.mappings.return_value.first.return_value = {
        "processed_count": 2,
        "error_count": 1,
    }

    update_result = Mock()
    db.execute.side_effect = [job_row_result, counts_result, update_result]

    rss_scraping_db_client_module.refresh_rss_scrape_job_status(db, job_id="job-1")

    assert db.execute.call_count == 3
    update_params = db.execute.call_args_list[2].args[1]
    assert update_params == {"job_id": "job-1", "status": "completed_with_errors"}
