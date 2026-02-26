from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.clients.database.source_ingest_db_client as source_ingest_db_client_module
from app.schemas.worker_result_schema import WorkerResultSchema, WorkerSourceSchema


def _build_payload(*, status: str = "success") -> WorkerResultSchema:
    return WorkerResultSchema(
        job_id="job-1",
        ingest=True,
        feed_id=10,
        feed_url="https://example.com/rss.xml",
        status=status,
        fetchprotection=1,
        sources=[
            WorkerSourceSchema(
                title="Article A",
                url="https://example.com/article-a",
                summary="summary",
                author="author",
                published_at=None,
                image_url="https://example.com/image.jpg",
            )
        ],
    )


def test_upsert_sources_for_feed_returns_early_for_non_success_status() -> None:
    db = Mock(spec=Session)

    source_ingest_db_client_module.upsert_sources_for_feed(
        db,
        payload=_build_payload(status="error"),
    )

    db.execute.assert_not_called()


def test_normalize_published_at_handles_none_naive_and_aware_values() -> None:
    naive_datetime = datetime(2026, 2, 26, 12, 0)
    aware_datetime = datetime(2026, 2, 26, 12, 0, tzinfo=timezone(timedelta(hours=2)))

    assert (
        source_ingest_db_client_module._normalize_published_at(None)
        == source_ingest_db_client_module.SOURCE_PUBLISHED_AT_FALLBACK
    )
    assert source_ingest_db_client_module._normalize_published_at(naive_datetime) == datetime(
        2026, 2, 26, 12, 0, tzinfo=timezone.utc
    )
    assert source_ingest_db_client_module._normalize_published_at(aware_datetime) == datetime(
        2026, 2, 26, 10, 0, tzinfo=timezone.utc
    )


def test_upsert_sources_for_feed_links_source_to_feed() -> None:
    db = Mock(spec=Session)
    payload = _build_payload(status="success")

    first_execute = Mock()
    first_execute.mappings.return_value.first.return_value = {
        "id": 77,
        "published_at": source_ingest_db_client_module.SOURCE_PUBLISHED_AT_FALLBACK,
    }
    second_execute = Mock()
    db.execute.side_effect = [first_execute, second_execute]

    source_ingest_db_client_module.upsert_sources_for_feed(db, payload=payload)

    assert db.execute.call_count == 2

    insert_source_params = db.execute.call_args_list[0].args[1]
    assert insert_source_params["published_at"] == source_ingest_db_client_module.SOURCE_PUBLISHED_AT_FALLBACK

    insert_link_params = db.execute.call_args_list[1].args[1]
    assert insert_link_params == {
        "source_id": 77,
        "feed_id": 10,
        "published_at": source_ingest_db_client_module.SOURCE_PUBLISHED_AT_FALLBACK,
    }
