from unittest.mock import Mock

import app.services.internal.rss_worker_task_service as rss_worker_task_service_module


def _query_text(query) -> str:
    return query.text if hasattr(query, "text") else str(query)


def _build_result_event(
    *,
    status: str,
    ingest: bool,
    error_message: str | None = None,
    resolved_fetchprotection: int | None = None,
) -> dict:
    return {
        "payload": {
            "job_id": "job-1",
            "ingest": ingest,
            "feed_id": 11,
            "feed_url": "https://example.com/feed.xml",
            "status": status,
            "error_message": error_message,
            "new_etag": "etag-1",
            "new_last_update": "2026-03-10T15:00:00Z",
            "fetchprotection": 1,
            "resolved_fetchprotection": resolved_fetchprotection,
            "sources": [
                {
                    "title": "Source title",
                    "url": "https://example.com/article",
                    "summary": "Summary",
                }
            ],
        }
    }


def test_complete_scrape_task_casts_null_error_stage_on_success(monkeypatch) -> None:
    db = Mock()
    execute_calls: list[tuple[str, dict | None]] = []

    def fake_execute(query, params=None):
        execute_calls.append((_query_text(query), params))
        return Mock()

    db.execute.side_effect = fake_execute
    monkeypatch.setattr(rss_worker_task_service_module, "open_db_session", lambda: db)
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "get_worker_instance_id",
        lambda _db, *, worker_type, worker_name: 7,
    )
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "_get_execution_row",
        lambda _db, *, task_id, execution_id: {
            "worker_instance_id": 7,
            "job_id": "job-1",
            "job_kind": "rss_scrape_ingest",
        },
    )
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "_list_task_feed_ids",
        lambda _db, *, task_id: {11},
    )
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "complete_rss_scrape_task_summary",
        lambda _db, *, task_id, feeds_processed, feeds_success, feeds_error: {
            "feeds_processed": feeds_processed
        },
    )
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "increment_rss_scrape_job_status",
        lambda _db, *, job_id, tasks_processed_delta, items_processed_delta, items_success_delta, items_error_delta: None,
    )
    update_calls: list[bool] = []
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "upsert_feed_scraping_state",
        lambda _db, *, payload, apply_resolved_fetchprotection: update_calls.append(
            apply_resolved_fetchprotection
        ),
    )
    source_upserts: list[int] = []
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "upsert_sources_for_results",
        lambda _db, *, payloads: source_upserts.extend(payload.feed_id for payload in payloads),
    )

    rss_worker_task_service_module.complete_scrape_task(
        worker_identity_id=1,
        worker_id="worker-1",
        task_id=1,
        execution_id=2,
        result_events=[_build_result_event(status="success", ingest=True)],
    )

    execution_update_sql, execution_update_params = next(
        (sql, params)
        for sql, params in execute_calls
        if "UPDATE rss_scrape_task_executions" in sql
    )
    assert "CAST(:error_stage AS worker_execution_error_stage_enum)" in execution_update_sql
    assert execution_update_params["outcome"] == "success"
    assert execution_update_params["error_stage"] is None
    assert execution_update_params["error_message"] is None
    assert update_calls == [False]
    assert source_upserts == [11]
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    db.close.assert_called_once()


def test_complete_scrape_task_check_job_writes_sources_and_updates_fetchprotection(monkeypatch) -> None:
    db = Mock()
    execute_calls: list[tuple[str, dict | None]] = []

    def fake_execute(query, params=None):
        execute_calls.append((_query_text(query), params))
        return Mock()

    db.execute.side_effect = fake_execute
    monkeypatch.setattr(rss_worker_task_service_module, "open_db_session", lambda: db)
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "get_worker_instance_id",
        lambda _db, *, worker_type, worker_name: 7,
    )
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "_get_execution_row",
        lambda _db, *, task_id, execution_id: {
            "worker_instance_id": 7,
            "job_id": "job-1",
            "job_kind": "rss_scrape_check",
        },
    )
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "_list_task_feed_ids",
        lambda _db, *, task_id: {11},
    )
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "complete_rss_scrape_task_summary",
        lambda _db, *, task_id, feeds_processed, feeds_success, feeds_error: {
            "feeds_processed": feeds_processed
        },
    )
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "increment_rss_scrape_job_status",
        lambda _db, *, job_id, tasks_processed_delta, items_processed_delta, items_success_delta, items_error_delta: None,
    )
    update_calls: list[bool] = []
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "upsert_feed_scraping_state",
        lambda _db, *, payload, apply_resolved_fetchprotection: update_calls.append(
            apply_resolved_fetchprotection
        ),
    )
    source_upserts: list[int] = []
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "upsert_sources_for_results",
        lambda _db, *, payloads: source_upserts.extend(payload.feed_id for payload in payloads),
    )

    rss_worker_task_service_module.complete_scrape_task(
        worker_identity_id=1,
        worker_id="worker-1",
        task_id=1,
        execution_id=2,
        result_events=[
            _build_result_event(
                status="success",
                ingest=False,
                resolved_fetchprotection=2,
            )
        ],
    )

    execution_update_sql, execution_update_params = next(
        (sql, params)
        for sql, params in execute_calls
        if "UPDATE rss_scrape_task_executions" in sql
    )
    assert "CAST(:error_stage AS worker_execution_error_stage_enum)" in execution_update_sql
    assert execution_update_params["outcome"] == "success"
    assert execution_update_params["error_stage"] is None
    assert execution_update_params["error_message"] is None
    assert update_calls == [True]
    assert source_upserts == [11]
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    db.close.assert_called_once()


def test_complete_scrape_task_casts_error_stage_on_feed_failure(monkeypatch) -> None:
    db = Mock()
    execute_calls: list[tuple[str, dict | None]] = []

    def fake_execute(query, params=None):
        execute_calls.append((_query_text(query), params))
        return Mock()

    db.execute.side_effect = fake_execute
    monkeypatch.setattr(rss_worker_task_service_module, "open_db_session", lambda: db)
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "get_worker_instance_id",
        lambda _db, *, worker_type, worker_name: 7,
    )
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "_get_execution_row",
        lambda _db, *, task_id, execution_id: {
            "worker_instance_id": 7,
            "job_id": "job-1",
            "job_kind": "rss_scrape_check",
        },
    )
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "_list_task_feed_ids",
        lambda _db, *, task_id: {11},
    )
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "complete_rss_scrape_task_summary",
        lambda _db, *, task_id, feeds_processed, feeds_success, feeds_error: {
            "feeds_processed": feeds_processed
        },
    )
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "increment_rss_scrape_job_status",
        lambda _db, *, job_id, tasks_processed_delta, items_processed_delta, items_success_delta, items_error_delta: None,
    )
    update_calls: list[bool] = []
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "upsert_feed_scraping_state",
        lambda _db, *, payload, apply_resolved_fetchprotection: update_calls.append(
            apply_resolved_fetchprotection
        ),
    )
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "upsert_sources_for_results",
        lambda _db, *, payloads: None,
    )

    rss_worker_task_service_module.complete_scrape_task(
        worker_identity_id=1,
        worker_id="worker-1",
        task_id=1,
        execution_id=2,
        result_events=[
            _build_result_event(
                status="error",
                ingest=False,
                error_message="network timeout",
            )
        ],
    )

    execution_update_sql, execution_update_params = next(
        (sql, params)
        for sql, params in execute_calls
        if "UPDATE rss_scrape_task_executions" in sql
    )
    assert "CAST(:error_stage AS worker_execution_error_stage_enum)" in execution_update_sql
    assert execution_update_params["outcome"] == "error"
    assert execution_update_params["error_stage"] == "fetch_feed"
    assert execution_update_params["error_message"] == "One or more feeds failed in batch"
    assert update_calls == [True]
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    db.close.assert_called_once()


def test_fail_scrape_task_casts_worker_loop_error_stage(monkeypatch) -> None:
    db = Mock()
    execute_calls: list[tuple[str, dict | None]] = []

    def fake_execute(query, params=None):
        execute_calls.append((_query_text(query), params))
        return Mock()

    db.execute.side_effect = fake_execute
    monkeypatch.setattr(rss_worker_task_service_module, "open_db_session", lambda: db)
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "get_worker_instance_id",
        lambda _db, *, worker_type, worker_name: 7,
    )
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "_get_execution_row",
        lambda _db, *, task_id, execution_id: {
            "worker_instance_id": 7,
            "job_id": "job-1",
        },
    )
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "_refresh_rss_task_summary",
        lambda _db, *, task_id, terminal_status: {"feeds_processed": 0},
    )
    monkeypatch.setattr(
        rss_worker_task_service_module,
        "refresh_rss_scrape_job_status",
        lambda _db, *, job_id: None,
    )

    rss_worker_task_service_module.fail_scrape_task(
        worker_identity_id=1,
        worker_id="worker-1",
        task_id=1,
        execution_id=2,
        error_message="worker crashed",
    )

    execution_update_sql, execution_update_params = next(
        (sql, params)
        for sql, params in execute_calls
        if "UPDATE rss_scrape_task_executions" in sql
    )
    assert "CAST(:error_stage AS worker_execution_error_stage_enum)" in execution_update_sql
    assert execution_update_params["error_stage"] == "worker_loop"
    assert execution_update_params["error_message"] == "worker crashed"
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    db.close.assert_called_once()


def test_refresh_rss_task_summary_casts_status_to_worker_task_status_enum() -> None:
    db = Mock()
    execute_calls: list[tuple[str, dict | None]] = []

    def fake_execute(query, params=None):
        execute_calls.append((_query_text(query), params))
        if "SELECT" in _query_text(query):
            result = Mock()
            result.mappings.return_value.one.return_value = {
                "feeds_total": 1,
                "feeds_processed": 1,
                "feeds_success": 1,
                "feeds_error": 0,
            }
            return result
        return Mock()

    db.execute.side_effect = fake_execute

    rss_worker_task_service_module._refresh_rss_task_summary(
        db,
        task_id=1,
        terminal_status="completed",
    )

    update_sql, update_params = next(
        (sql, params)
        for sql, params in execute_calls
        if "UPDATE rss_scrape_tasks" in sql
    )
    assert "CAST(:status AS worker_task_status_enum)" in update_sql
    assert update_params["status"] == "completed"
