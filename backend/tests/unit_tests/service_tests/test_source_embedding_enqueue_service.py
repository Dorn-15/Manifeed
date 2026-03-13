from datetime import datetime, timezone
from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.services.sources.source_embedding_enqueue_service as source_embedding_enqueue_service_module


def test_enqueue_sources_without_embeddings_returns_zero_when_nothing_matches(monkeypatch) -> None:
    db = Mock(spec=Session)
    monkeypatch.setattr(
        source_embedding_enqueue_service_module,
        "resolve_embedding_model_name",
        lambda: "intfloat/multilingual-e5-large",
    )
    monkeypatch.setattr(
        source_embedding_enqueue_service_module,
        "list_rss_sources_without_embeddings",
        lambda _db, *, model_name, reembed_model_mismatches: [],
    )

    result = source_embedding_enqueue_service_module.enqueue_sources_without_embeddings(db)

    assert result.queued_sources == 0
    db.commit.assert_not_called()


def test_enqueue_sources_without_embeddings_forwards_reembed_flag(monkeypatch) -> None:
    db = Mock(spec=Session)
    requested_at = datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        source_embedding_enqueue_service_module,
        "resolve_embedding_model_name",
        lambda: "intfloat/multilingual-e5-large",
    )
    monkeypatch.setattr(
        source_embedding_enqueue_service_module,
        "list_rss_sources_without_embeddings",
        lambda _db, *, model_name, reembed_model_mismatches: [{"id": 1}] if reembed_model_mismatches else [],
    )
    monkeypatch.setattr(
        source_embedding_enqueue_service_module,
        "create_source_embedding_job",
        lambda _db, *, requested_by, requested_at, initial_status, tasks_total, items_total: "embedding-job-1",
    )
    enqueue_calls = []
    monkeypatch.setattr(
        source_embedding_enqueue_service_module,
        "enqueue_source_embedding_tasks",
        lambda _db, *, job_id, model_name, requested_at, sources: enqueue_calls.append((job_id, model_name, len(sources))),
    )

    class _FakeDatetime:
        @staticmethod
        def now(tz=None):
            return requested_at

    monkeypatch.setattr(source_embedding_enqueue_service_module, "datetime", _FakeDatetime)

    result = source_embedding_enqueue_service_module.enqueue_sources_without_embeddings(
        db,
        reembed_model_mismatches=True,
    )

    assert result.queued_sources == 1
    assert result.job_id == "embedding-job-1"
    assert result.tasks_total == 1
    assert result.items_total == 1
    assert enqueue_calls == [("embedding-job-1", "intfloat/multilingual-e5-large", 1)]
    db.commit.assert_called_once()
