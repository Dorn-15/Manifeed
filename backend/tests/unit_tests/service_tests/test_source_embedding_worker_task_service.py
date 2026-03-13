from unittest.mock import Mock

import app.services.internal.source_embedding_worker_task_service as source_embedding_worker_task_service_module


def _query_text(query) -> str:
    return query.text if hasattr(query, "text") else str(query)


def test_complete_embedding_task_casts_null_error_stage_on_success(monkeypatch) -> None:
    db = Mock()
    execute_calls: list[tuple[str, dict | None]] = []

    def fake_execute(query, params=None):
        execute_calls.append((_query_text(query), params))
        return Mock()

    db.execute.side_effect = fake_execute
    monkeypatch.setattr(source_embedding_worker_task_service_module, "open_db_session", lambda: db)
    monkeypatch.setattr(
        source_embedding_worker_task_service_module,
        "_get_execution_row",
        lambda _db, *, task_id, execution_id: {
            "worker_instance_id": 8,
            "job_id": "job-1",
            "model_name": "e5-small",
        },
    )
    monkeypatch.setattr(
        source_embedding_worker_task_service_module,
        "_list_task_source_ids",
        lambda _db, *, task_id: {101},
    )
    monkeypatch.setattr(
        source_embedding_worker_task_service_module,
        "_refresh_embedding_task_summary",
        lambda _db, *, task_id, terminal_status: {"sources_processed": 1},
    )
    monkeypatch.setattr(
        source_embedding_worker_task_service_module,
        "_refresh_worker_job_status",
        lambda _db, *, job_id: None,
    )
    monkeypatch.setattr(
        source_embedding_worker_task_service_module,
        "upsert_source_embeddings",
        lambda _db, *, payload: None,
    )
    monkeypatch.setattr(
        source_embedding_worker_task_service_module,
        "upsert_worker_instance_state",
        lambda *_args, **_kwargs: 8,
    )

    source_embedding_worker_task_service_module.complete_embedding_task(
        worker_identity_id=3,
        worker_id="device-embedding-1",
        task_id=1,
        execution_id=2,
        result_payload={
            "sources": [{"id": 101, "embedding": [0.1, 0.2]}],
        },
    )

    execution_update_sql, execution_update_params = next(
        (sql, params)
        for sql, params in execute_calls
        if "UPDATE source_embedding_task_executions" in sql
    )
    assert "CAST(NULL AS worker_execution_error_stage_enum)" in execution_update_sql
    assert execution_update_params["execution_id"] == 2
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    db.close.assert_called_once()


def test_fail_embedding_task_casts_error_stage_parameter_to_enum(monkeypatch) -> None:
    db = Mock()
    execute_calls: list[tuple[str, dict | None]] = []

    def fake_execute(query, params=None):
        execute_calls.append((_query_text(query), params))
        return Mock()

    db.execute.side_effect = fake_execute
    monkeypatch.setattr(source_embedding_worker_task_service_module, "open_db_session", lambda: db)
    monkeypatch.setattr(
        source_embedding_worker_task_service_module,
        "_get_execution_row",
        lambda _db, *, task_id, execution_id: {
            "worker_instance_id": 8,
            "job_id": "job-1",
            "model_name": "e5-small",
        },
    )
    monkeypatch.setattr(
        source_embedding_worker_task_service_module,
        "_refresh_embedding_task_summary",
        lambda _db, *, task_id, terminal_status: {"sources_processed": 0},
    )
    monkeypatch.setattr(
        source_embedding_worker_task_service_module,
        "_refresh_worker_job_status",
        lambda _db, *, job_id: None,
    )
    monkeypatch.setattr(
        source_embedding_worker_task_service_module,
        "upsert_worker_instance_state",
        lambda *_args, **_kwargs: 8,
    )

    source_embedding_worker_task_service_module.fail_embedding_task(
        worker_identity_id=3,
        worker_id="device-embedding-1",
        task_id=1,
        execution_id=2,
        error_message="invalid payload from worker",
    )

    execution_update_sql, execution_update_params = next(
        (sql, params)
        for sql, params in execute_calls
        if "UPDATE source_embedding_task_executions" in sql
    )
    assert "CAST(:error_stage AS worker_execution_error_stage_enum)" in execution_update_sql
    assert execution_update_params["error_stage"] == "invalid_payload"
    assert execution_update_params["error_message"] == "invalid payload from worker"
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    db.close.assert_called_once()


def test_refresh_embedding_task_summary_casts_status_to_worker_task_status_enum() -> None:
    db = Mock()
    execute_calls: list[tuple[str, dict | None]] = []

    def fake_execute(query, params=None):
        execute_calls.append((_query_text(query), params))
        if "SELECT" in _query_text(query):
            result = Mock()
            result.mappings.return_value.one.return_value = {
                "sources_total": 1,
                "sources_processed": 1,
                "sources_success": 1,
                "sources_error": 0,
            }
            return result
        return Mock()

    db.execute.side_effect = fake_execute

    source_embedding_worker_task_service_module._refresh_embedding_task_summary(
        db,
        task_id=1,
        terminal_status="completed",
    )

    update_sql, update_params = next(
        (sql, params)
        for sql, params in execute_calls
        if "UPDATE source_embedding_tasks" in sql
    )
    assert "CAST(:status AS worker_task_status_enum)" in update_sql
    assert update_params["status"] == "completed"


def test_refresh_worker_job_status_casts_status_to_worker_job_status_enum() -> None:
    db = Mock()
    execute_calls: list[tuple[str, dict | None]] = []

    def fake_execute(query, params=None):
        execute_calls.append((_query_text(query), params))
        if "SELECT" in _query_text(query):
            result = Mock()
            result.mappings.return_value.one.return_value = {
                "tasks_total": 1,
                "tasks_processed": 1,
                "items_total": 1,
                "items_processed": 1,
                "items_success": 1,
                "items_error": 0,
                "processing_count": 0,
                "pending_count": 0,
                "failed_task_count": 0,
            }
            return result
        return Mock()

    db.execute.side_effect = fake_execute

    source_embedding_worker_task_service_module._refresh_worker_job_status(
        db,
        job_id="job-1",
    )

    update_sql, update_params = next(
        (sql, params)
        for sql, params in execute_calls
        if "UPDATE worker_jobs" in sql
    )
    assert "CAST(:status AS worker_job_status_enum)" in update_sql
    assert update_params["status"] == "completed"
