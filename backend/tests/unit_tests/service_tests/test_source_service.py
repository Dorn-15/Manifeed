from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.services.sources.source_service as source_service_module
from app.schemas.sources import RssSourceDetailRead, RssSourceRead


def test_get_rss_sources_builds_paginated_response(monkeypatch) -> None:
    db = Mock(spec=Session)
    expected_items = [
        RssSourceRead(
            id=5,
            title="Article",
            summary="Summary",
            author="Jane",
            url="https://example.com/a",
            company_names=["ACME"],
        )
    ]

    def fake_list_rss_sources_read(db, limit, offset, feed_id=None, company_id=None):
        assert feed_id == 2
        assert company_id is None
        assert limit == 20
        assert offset == 40
        return expected_items, 73

    monkeypatch.setattr(source_service_module, "list_rss_sources_read", fake_list_rss_sources_read)

    result = source_service_module.get_rss_sources(
        db,
        limit=20,
        offset=40,
        feed_id=2,
    )

    assert result.items == expected_items
    assert result.total == 73
    assert result.limit == 20
    assert result.offset == 40


def test_get_rss_source_by_id_returns_client_result(monkeypatch) -> None:
    db = Mock(spec=Session)
    expected = RssSourceDetailRead(
        id=9,
        title="Source",
        url="https://example.com/s/9",
        company_names=["ACME"],
        feed_sections=["Main"],
    )

    monkeypatch.setattr(
        source_service_module,
        "get_rss_source_detail_read_by_id",
        lambda _db, source_id: expected if source_id == 9 else None,
    )

    result = source_service_module.get_rss_source_by_id(db, source_id=9)

    assert result == expected
