from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.clients.database.sources.manage_source_partitions_db_cli as source_partition_db_cli_module
import app.services.sources.source_partition_service as source_partition_service_module


def test_repartition_rss_source_partitions_commits_and_returns_schema(monkeypatch) -> None:
    db = Mock(spec=Session)

    monkeypatch.setattr(
        source_partition_service_module,
        "repartition_default_sources_by_published_at",
        lambda _db: source_partition_db_cli_module.SourcePartitionMaintenanceResult(
            source_default_rows_repartitioned=3,
            source_feed_default_rows_repartitioned=4,
            source_weekly_partitions_created=2,
            source_feed_weekly_partitions_created=2,
            weeks_covered=2,
        ),
    )

    result = source_partition_service_module.repartition_rss_source_partitions(db)

    assert result.status == "completed"
    assert result.source_default_rows_repartitioned == 3
    assert result.source_feed_default_rows_repartitioned == 4
    assert result.source_weekly_partitions_created == 2
    assert result.source_feed_weekly_partitions_created == 2
    assert result.weeks_covered == 2
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_repartition_rss_source_partitions_rolls_back_on_failure(monkeypatch) -> None:
    db = Mock(spec=Session)

    def fail_repartition(_db):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        source_partition_service_module,
        "repartition_default_sources_by_published_at",
        fail_repartition,
    )

    try:
        source_partition_service_module.repartition_rss_source_partitions(db)
    except RuntimeError as exception:
        assert str(exception) == "boom"
    else:
        raise AssertionError("Expected RuntimeError")

    db.commit.assert_not_called()
    db.rollback.assert_called_once()
