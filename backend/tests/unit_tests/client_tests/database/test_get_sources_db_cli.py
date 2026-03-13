from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.clients.database.sources.get_sources_db_cli as get_sources_db_cli_module


def test_list_rss_sources_without_embeddings_maps_rows_to_schema() -> None:
    db = Mock(spec=Session)

    execute_result = Mock()
    execute_result.mappings.return_value.all.return_value = [
        {
            "id": 10,
            "title": "Article A",
            "summary": "Summary A",
            "url": "https://example.com/a",
        },
        {
            "id": 11,
            "title": "Article B",
            "summary": None,
            "url": "https://example.com/b",
        },
    ]
    db.execute.return_value = execute_result

    results = get_sources_db_cli_module.list_rss_sources_without_embeddings(
        db,
        model_name="intfloat/multilingual-e5-large",
        reembed_model_mismatches=False,
    )

    assert len(results) == 2
    assert results[0].id == 10
    assert results[0].title == "Article A"
    assert results[0].summary == "Summary A"
    assert results[0].url == "https://example.com/a"
    assert results[1].id == 11
    assert results[1].title == "Article B"
    assert results[1].summary is None
    assert results[1].url == "https://example.com/b"
    db.execute.assert_called_once()
    _, query_params = db.execute.call_args.args
    assert query_params == {
        "model_name": "intfloat/multilingual-e5-large",
        "reembed_model_mismatches": False,
    }
