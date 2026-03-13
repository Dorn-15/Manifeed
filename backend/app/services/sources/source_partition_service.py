from sqlalchemy.orm import Session

from app.clients.database import repartition_default_sources_by_published_at
from app.schemas.sources import RssSourcePartitionMaintenanceRead


def repartition_rss_source_partitions(
    db: Session,
) -> RssSourcePartitionMaintenanceRead:
    try:
        result = repartition_default_sources_by_published_at(db)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return RssSourcePartitionMaintenanceRead(
        source_default_rows_repartitioned=result.source_default_rows_repartitioned,
        source_feed_default_rows_repartitioned=result.source_feed_default_rows_repartitioned,
        source_weekly_partitions_created=result.source_weekly_partitions_created,
        source_feed_weekly_partitions_created=result.source_feed_weekly_partitions_created,
        weeks_covered=result.weeks_covered,
    )
