from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy.orm import Session

from app.clients.database.sources import (
    get_rss_source_detail_read_by_id,
    list_rss_sources_read,
)


def test_list_rss_sources_read_returns_items_and_total() -> None:
    mock_db = Mock(spec=Session)

    rows_result = Mock()
    rows_result.mappings.return_value.all.return_value = [
        {
            "id": 3,
            "title": "Source title",
            "summary": "Source summary",
            "url": "https://example.com/source",
            "published_at": None,
            "image_url": "https://example.com/image.jpg",
            "company_name": "The Verge",
        }
    ]
    count_result = Mock()
    count_result.scalar_one.return_value = 22
    mock_db.execute.side_effect = [rows_result, count_result]

    items, total = list_rss_sources_read(
        mock_db,
        limit=12,
        offset=0,
    )

    assert len(items) == 1
    assert items[0].id == 3
    assert items[0].company_name == "The Verge"
    assert total == 22
    assert mock_db.execute.call_count == 2


def test_get_rss_source_detail_read_by_id_maps_company_and_sections() -> None:
    mock_db = Mock(spec=Session)
    source = SimpleNamespace(
        id=9,
        title="Source detail",
        summary="Detail summary",
        url="https://example.com/detail",
        published_at=None,
        image_url="https://example.com/detail.jpg",
        feed_links=[
            SimpleNamespace(
                feed=SimpleNamespace(
                    section="Main",
                    company=SimpleNamespace(name="The Verge"),
                )
            ),
            SimpleNamespace(
                feed=SimpleNamespace(
                    section="AI",
                    company=SimpleNamespace(name="The Verge"),
                )
            ),
            SimpleNamespace(
                feed=SimpleNamespace(
                    section="Main",
                    company=SimpleNamespace(name="The Verge"),
                )
            ),
        ],
    )

    mock_db.execute.return_value.scalar_one_or_none.return_value = source

    detail = get_rss_source_detail_read_by_id(mock_db, source_id=9)

    assert detail is not None
    assert detail.id == 9
    assert detail.company_name == "The Verge"
    assert detail.feed_sections == ["AI", "Main"]


def test_get_rss_source_detail_read_by_id_returns_none_when_missing() -> None:
    mock_db = Mock(spec=Session)
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    detail = get_rss_source_detail_read_by_id(mock_db, source_id=99)

    assert detail is None
