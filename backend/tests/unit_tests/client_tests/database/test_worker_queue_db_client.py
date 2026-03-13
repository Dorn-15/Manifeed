from datetime import datetime, timezone
from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.clients.database.worker_queue_db_client as worker_queue_db_client_module
from app.schemas.rss import RssScrapeFeedPayloadSchema


def test_enqueue_rss_scrape_tasks_creates_one_task_per_batch() -> None:
    db = Mock(spec=Session)
    first_insert = Mock()
    first_insert.scalar_one.return_value = 101
    second_insert = Mock()
    second_insert.scalar_one.return_value = 102
    db.execute.side_effect = [first_insert, None, second_insert, None]

    task_count = worker_queue_db_client_module.enqueue_rss_scrape_tasks(
        db,
        job_id="job-1",
        requested_at=datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc),
        feed_batches=[
            [
                RssScrapeFeedPayloadSchema(feed_id=1, feed_url="https://example.com/1.xml", company_id=10),
                RssScrapeFeedPayloadSchema(feed_id=2, feed_url="https://example.com/2.xml", company_id=10),
            ],
            [
                RssScrapeFeedPayloadSchema(feed_id=3, feed_url="https://example.com/3.xml", company_id=20),
            ],
        ],
    )

    assert task_count == 2
    assert db.execute.call_count == 4
    _, first_items_params = db.execute.call_args_list[1].args
    _, second_items_params = db.execute.call_args_list[3].args
    assert [item["feed_id"] for item in first_items_params] == [1, 2]
    assert [item["feed_id"] for item in second_items_params] == [3]


def test_resolve_rss_scrape_task_batch_size_clamps_to_twenty(monkeypatch) -> None:
    monkeypatch.setenv("RSS_SCRAPE_TASK_BATCH_SIZE", "50")

    assert worker_queue_db_client_module.resolve_rss_scrape_task_batch_size() == 20
