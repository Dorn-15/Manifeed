from .get_rss_feeds_db_cli import (
    list_rss_feeds,
    list_rss_feeds_read,
    list_rss_feeds_by_urls,
    list_enabled_rss_feeds,
    get_rss_feed_by_id,
)

from .utils_rss_feeds_db_cli import (
    upsert_feed,
    link_company_to_feed,
    delete_company_feeds_not_in_urls,
    set_rss_feed_enabled,
    set_rss_company_enabled,
)

from .rss_company_db_cli import (
    delete_rss_companies_without_feeds,
    get_company_by_id,
    get_company_by_name,
    get_or_create_company,
    list_rss_company_ids_with_feeds,
)

from .rss_catalog_sync_database_client import (
    get_rss_catalog_sync_state,
    mark_rss_catalog_sync_failure,
    mark_rss_catalog_sync_success,
)

from .rss_tags_db_cli import (
    get_or_create_tags,
)
from .rss_scrape_job_database_client import (
    create_rss_scrape_job,
    get_rss_scrape_job_status_read,
    list_rss_feed_scrape_payloads,
    list_rss_scrape_job_feed_reads,
)

__all__ = [
    "list_rss_feeds",
    "list_rss_feeds_read",
    "list_rss_feeds_by_urls",
    "list_enabled_rss_feeds",
    "get_rss_feed_by_id",
    "upsert_feed",
    "link_company_to_feed",
    "delete_company_feeds_not_in_urls",
    "set_rss_feed_enabled",
    "set_rss_company_enabled",
    # Tags
    "get_or_create_tags",
    # Companies
    "delete_rss_companies_without_feeds",
    "get_company_by_id",
    "get_company_by_name",
    "get_or_create_company",
    "list_rss_company_ids_with_feeds",
    # Catalog sync
    "get_rss_catalog_sync_state",
    "mark_rss_catalog_sync_failure",
    "mark_rss_catalog_sync_success",
    # Scrape jobs
    "create_rss_scrape_job",
    "get_rss_scrape_job_status_read",
    "list_rss_feed_scrape_payloads",
    "list_rss_scrape_job_feed_reads",
]
