from datetime import datetime, timezone
from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.clients.database.source_ingest_db_client as source_ingest_db_client_module
from app.schemas import WorkerResultSchema


def test_upsert_sources_for_feed_truncates_bounded_content_fields() -> None:
    db = Mock(spec=Session)

    company_lookup_row = Mock()
    company_lookup_row.mappings.return_value.all.return_value = [
        {"feed_id": 11, "company_name": None}
    ]
    url_lookup_row = Mock()
    url_lookup_row.mappings.return_value.all.return_value = []
    source_row = Mock()
    source_row.mappings.return_value.one_or_none.return_value = {
        "id": 10,
        "ingested_at": datetime(2026, 3, 10, 19, 0, tzinfo=timezone.utc),
    }
    db.execute.side_effect = [
        company_lookup_row,
        url_lookup_row,
        source_row,
        Mock(),
        Mock(),
    ]

    source_ingest_db_client_module.upsert_sources_for_feed(
        db,
        payload=WorkerResultSchema.model_validate(
            {
                "job_id": "job-1",
                "ingest": True,
                "feed_id": 11,
                "feed_url": "https://example.com/feed.xml",
                "status": "success",
                "error_message": None,
                "new_etag": None,
                "new_last_update": None,
                "fetchprotection": 1,
                "resolved_fetchprotection": 1,
                "sources": [
                    {
                        "title": "T" * 550,
                        "url": "https://example.com/article",
                        "summary": "Summary",
                        "author": "A" * 300,
                        "image_url": f"https://example.com/{'i' * 1100}",
                    }
                ],
            }
        ),
    )

    _, content_insert_params = db.execute.call_args_list[3].args
    assert len(content_insert_params["title"]) == source_ingest_db_client_module.SOURCE_TITLE_MAX_LENGTH
    assert len(content_insert_params["author"]) == source_ingest_db_client_module.SOURCE_AUTHOR_MAX_LENGTH
    assert len(content_insert_params["image_url"]) == source_ingest_db_client_module.SOURCE_IMAGE_URL_MAX_LENGTH
    assert content_insert_params["summary"] == "Summary"


def test_upsert_sources_for_feed_keeps_optional_fields_none() -> None:
    db = Mock(spec=Session)

    company_lookup_row = Mock()
    company_lookup_row.mappings.return_value.all.return_value = [
        {"feed_id": 11, "company_name": None}
    ]
    url_lookup_row = Mock()
    url_lookup_row.mappings.return_value.all.return_value = []
    source_row = Mock()
    source_row.mappings.return_value.one_or_none.return_value = {
        "id": 10,
        "ingested_at": datetime(2026, 3, 10, 19, 0, tzinfo=timezone.utc),
    }
    db.execute.side_effect = [
        company_lookup_row,
        url_lookup_row,
        source_row,
        Mock(),
        Mock(),
    ]

    source_ingest_db_client_module.upsert_sources_for_feed(
        db,
        payload=WorkerResultSchema.model_validate(
            {
                "job_id": "job-1",
                "ingest": True,
                "feed_id": 11,
                "feed_url": "https://example.com/feed.xml",
                "status": "success",
                "error_message": None,
                "new_etag": None,
                "new_last_update": None,
                "fetchprotection": 1,
                "resolved_fetchprotection": 1,
                "sources": [
                    {
                        "title": "Title",
                        "url": "https://example.com/article",
                        "summary": None,
                        "author": None,
                        "image_url": None,
                    }
                ],
            }
        ),
    )

    _, content_insert_params = db.execute.call_args_list[3].args
    assert content_insert_params["author"] is None
    assert content_insert_params["image_url"] is None


def test_upsert_sources_for_feed_reuses_source_when_title_and_company_match() -> None:
    db = Mock(spec=Session)

    company_lookup_row = Mock()
    company_lookup_row.mappings.return_value.all.return_value = [
        {"feed_id": 11, "company_name": "Le Monde"}
    ]
    url_lookup_row = Mock()
    url_lookup_row.mappings.return_value.all.return_value = []
    title_lookup_row = Mock()
    title_lookup_row.mappings.return_value.all.return_value = [
        {
            "id": 42,
            "ingested_at": datetime(2026, 3, 9, 10, 0, tzinfo=timezone.utc),
            "company_name": "Le  Monde",
            "title": "Titre du jour",
        }
    ]
    db.execute.side_effect = [
        company_lookup_row,
        url_lookup_row,
        title_lookup_row,
        Mock(),
        Mock(),
    ]

    source_ingest_db_client_module.upsert_sources_for_feed(
        db,
        payload=WorkerResultSchema.model_validate(
            {
                "job_id": "job-1",
                "ingest": True,
                "feed_id": 11,
                "feed_url": "https://example.com/feed.xml",
                "status": "success",
                "error_message": None,
                "new_etag": None,
                "new_last_update": None,
                "fetchprotection": 1,
                "resolved_fetchprotection": 1,
                "sources": [
                    {
                        "title": "Titre du jour",
                        "url": "https://example.com/article-different",
                        "summary": "Summary",
                        "author": "Alice",
                        "image_url": None,
                    }
                ],
            }
        ),
    )

    assert len(db.execute.call_args_list) == 5
    content_insert_call = db.execute.call_args_list[3]
    assert content_insert_call.args[1]["source_id"] == 42
    assert content_insert_call.args[1]["ingested_at"] == datetime(
        2026,
        3,
        9,
        10,
        0,
        tzinfo=timezone.utc,
    )

    link_insert_call = db.execute.call_args_list[4]
    assert link_insert_call.args[1]["source_id"] == 42


def test_build_source_ingest_operations_orders_globally_across_payloads() -> None:
    payloads = [
        WorkerResultSchema.model_validate(
            {
                "job_id": "job-1",
                "ingest": True,
                "feed_id": 12,
                "feed_url": "https://example.com/feed-2.xml",
                "status": "success",
                "error_message": None,
                "new_etag": None,
                "new_last_update": None,
                "fetchprotection": 1,
                "resolved_fetchprotection": 1,
                "sources": [
                    {
                        "title": "Zeta later",
                        "url": "https://example.com/zeta",
                        "published_at": "2026-03-10T12:00:00Z",
                    }
                ],
            }
        ),
        WorkerResultSchema.model_validate(
        {
            "job_id": "job-1",
            "ingest": True,
            "feed_id": 11,
            "feed_url": "https://example.com/feed-1.xml",
            "status": "success",
            "error_message": None,
            "new_etag": None,
            "new_last_update": None,
            "fetchprotection": 1,
            "resolved_fetchprotection": 1,
            "sources": [
                {
                    "title": "Alpha first",
                    "url": "https://example.com/alpha",
                    "published_at": "2026-03-10T12:00:00Z",
                },
                {
                    "title": "Zeta earlier",
                    "url": "https://example.com/zeta",
                    "published_at": "2026-03-09T12:00:00Z",
                },
            ],
        }
        ),
    ]

    operations = source_ingest_db_client_module._build_source_ingest_operations(
        payloads,
        feed_company_names={11: None, 12: None},
    )

    assert [(operation.source.url, operation.source.title, operation.feed_id) for operation in operations] == [
        ("https://example.com/alpha", "Alpha first", 11),
        ("https://example.com/zeta", "Zeta earlier", 11),
        ("https://example.com/zeta", "Zeta later", 12),
    ]


def test_resolve_or_create_source_uses_insert_do_nothing_then_select_fallback() -> None:
    db = Mock(spec=Session)
    insert_result = Mock()
    insert_result.mappings.return_value.one_or_none.return_value = None
    select_result = Mock()
    select_result.mappings.return_value.one_or_none.return_value = {
        "id": 99,
        "ingested_at": datetime(2026, 3, 10, 19, 0, tzinfo=timezone.utc),
    }
    db.execute.side_effect = [insert_result, select_result]

    resolved_source = source_ingest_db_client_module._resolve_or_create_source(
        db,
        url="https://example.com/article",
        title="Article",
        published_at=datetime(2026, 3, 10, 18, 0, tzinfo=timezone.utc),
        feed_company_name=None,
        existing_sources_by_identity={},
        title_company_cache={},
    )

    insert_query = db.execute.call_args_list[0].args[0]
    assert "ON CONFLICT (url, published_at) DO NOTHING" in str(insert_query)
    assert resolved_source["id"] == 99
