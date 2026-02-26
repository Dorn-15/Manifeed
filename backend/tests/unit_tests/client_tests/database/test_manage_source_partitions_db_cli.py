from datetime import datetime, timezone
from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.clients.database.sources.manage_source_partitions_db_cli as manage_source_partitions_db_cli_module


def test_repartition_default_sources_by_published_at_orchestrates_steps(monkeypatch) -> None:
    db = Mock(spec=Session)
    week_starts = [
        datetime(2026, 2, 16, tzinfo=timezone.utc),
        datetime(2026, 2, 23, tzinfo=timezone.utc),
    ]
    call_sequence: list[str] = []

    monkeypatch.setattr(
        manage_source_partitions_db_cli_module,
        "_prepare_default_partition_buffers",
        lambda _db: call_sequence.append("prepare"),
    )
    monkeypatch.setattr(
        manage_source_partitions_db_cli_module,
        "_count_table_rows",
        lambda _db, table_name: 5 if "sources_default" in table_name else 9,
    )
    monkeypatch.setattr(
        manage_source_partitions_db_cli_module,
        "_clear_default_partitions",
        lambda _db: call_sequence.append("clear"),
    )
    monkeypatch.setattr(
        manage_source_partitions_db_cli_module,
        "_list_week_starts_for_all_sources",
        lambda _db: week_starts,
    )

    def fake_create_weekly_partition_pair(_db, week_start):
        call_sequence.append(f"partition:{week_start.date().isoformat()}")
        if week_start == week_starts[0]:
            return True, True
        return False, True

    monkeypatch.setattr(
        manage_source_partitions_db_cli_module,
        "_create_weekly_partition_pair",
        fake_create_weekly_partition_pair,
    )
    monkeypatch.setattr(
        manage_source_partitions_db_cli_module,
        "_restore_sources_from_buffer",
        lambda _db: call_sequence.append("restore_sources"),
    )
    monkeypatch.setattr(
        manage_source_partitions_db_cli_module,
        "_restore_source_feeds_from_buffer",
        lambda _db: call_sequence.append("restore_source_feeds"),
    )
    monkeypatch.setattr(
        manage_source_partitions_db_cli_module,
        "_sync_sources_sequence",
        lambda _db: call_sequence.append("sync_sequence"),
    )

    result = manage_source_partitions_db_cli_module.repartition_default_sources_by_published_at(db)

    assert result.source_default_rows_repartitioned == 5
    assert result.source_feed_default_rows_repartitioned == 9
    assert result.source_weekly_partitions_created == 1
    assert result.source_feed_weekly_partitions_created == 2
    assert result.weeks_covered == 2
    assert call_sequence == [
        "prepare",
        "clear",
        "partition:2026-02-16",
        "partition:2026-02-23",
        "restore_sources",
        "restore_source_feeds",
        "sync_sequence",
    ]
