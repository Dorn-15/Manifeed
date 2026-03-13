from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.clients.database.rss.rss_company_db_cli as rss_company_db_cli_module


def test_list_rss_company_ids_with_feeds_returns_scalar_ids() -> None:
    db = Mock(spec=Session)
    execute_result = Mock()
    execute_result.scalars.return_value.all.return_value = [2, 5]
    db.execute.return_value = execute_result

    result = rss_company_db_cli_module.list_rss_company_ids_with_feeds(db)

    assert result == [2, 5]
    db.execute.assert_called_once()


def test_delete_rss_companies_without_feeds_deletes_all_orphans() -> None:
    db = Mock(spec=Session)
    select_result = Mock()
    select_result.scalars.return_value.all.return_value = [3, 7]
    delete_result = Mock()
    db.execute.side_effect = [select_result, delete_result]

    result = rss_company_db_cli_module.delete_rss_companies_without_feeds(db)

    assert result == 2
    assert db.execute.call_count == 2


def test_delete_rss_companies_without_feeds_returns_zero_when_none_found() -> None:
    db = Mock(spec=Session)
    select_result = Mock()
    select_result.scalars.return_value.all.return_value = []
    db.execute.return_value = select_result

    result = rss_company_db_cli_module.delete_rss_companies_without_feeds(db)

    assert result == 0
    db.execute.assert_called_once()
