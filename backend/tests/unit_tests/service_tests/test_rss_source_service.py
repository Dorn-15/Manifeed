from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.services.sources.source_service as rss_source_service_module
from app.schemas.sources import (
    RssSourceDetailRead,
    RssSourceRead,
)


def test_get_rss_sources_returns_paginated_payload(monkeypatch) -> None:
    mock_db = Mock(spec=Session)
    expected_items = [
        RssSourceRead(
            id=5,
            title="Source 5",
            summary="Summary 5",
            url="https://example.com/source-5",
            image_url=None,
            company_name="The Verge",
        )
    ]

    monkeypatch.setattr(
        rss_source_service_module,
        "list_rss_sources_read",
        lambda db, limit, offset, feed_id=None, company_id=None: (
            expected_items,
            31,
        )
        if db is mock_db and limit == 12 and offset == 24 else ([], 0),
    )

    result = rss_source_service_module.get_rss_sources(
        mock_db,
        limit=12,
        offset=24,
    )

    assert result.items == expected_items
    assert result.total == 31
    assert result.limit == 12
    assert result.offset == 24


def test_get_rss_sources_applies_feed_filter(monkeypatch) -> None:
    mock_db = Mock(spec=Session)

    monkeypatch.setattr(
        rss_source_service_module,
        "list_rss_sources_read",
        lambda db, limit, offset, feed_id=None, company_id=None: ([], 7)
        if db is mock_db and limit == 10 and offset == 0 and feed_id == 9 and company_id is None
        else ([], 0),
    )

    result = rss_source_service_module.get_rss_sources(
        mock_db,
        feed_id=9,
        limit=10,
        offset=0,
    )

    assert result.total == 7
    assert result.limit == 10
    assert result.offset == 0


def test_get_rss_sources_applies_company_filter(monkeypatch) -> None:
    mock_db = Mock(spec=Session)

    monkeypatch.setattr(
        rss_source_service_module,
        "list_rss_sources_read",
        lambda db, limit, offset, feed_id=None, company_id=None: ([], 4)
        if db is mock_db and limit == 8 and offset == 16 and feed_id is None and company_id == 2
        else ([], 0),
    )

    result = rss_source_service_module.get_rss_sources(
        mock_db,
        company_id=2,
        limit=8,
        offset=16,
    )

    assert result.total == 4
    assert result.limit == 8
    assert result.offset == 16


def test_get_rss_source_by_id_returns_detail(monkeypatch) -> None:
    mock_db = Mock(spec=Session)
    expected_detail = RssSourceDetailRead(
        id=13,
        title="Source 13",
        summary="Summary 13",
        url="https://example.com/source-13",
        image_url="https://example.com/source-13.jpg",
        company_name="Wired",
        feed_sections=["AI", "Main"],
    )

    monkeypatch.setattr(
        rss_source_service_module,
        "get_rss_source_detail_read_by_id",
        lambda db, source_id: expected_detail if db is mock_db and source_id == 13 else None,
    )

    result = rss_source_service_module.get_rss_source_by_id(
        mock_db,
        source_id=13,
    )

    assert result == expected_detail
