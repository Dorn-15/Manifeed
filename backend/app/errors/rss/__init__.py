from .custom_exceptions import (
    RssCatalogParseError,
    RssCompanyNotFoundError,
    RssFeedNotFoundError,
    RssFeedToggleForbiddenError,
    RssIconNotFoundError,
    RssRepositorySyncError,
)

from .exception_handlers import (
    rss_catalog_parse_error_handler,
    rss_company_not_found_error_handler,
    rss_feed_not_found_error_handler,
    rss_feed_toggle_forbidden_error_handler,
    rss_icon_not_found_error_handler,
    rss_repository_sync_error_handler,
)

__all__ = [
    # Custom exceptions
    "RssCatalogParseError",
    "RssCompanyNotFoundError",
    "RssFeedNotFoundError",
    "RssFeedToggleForbiddenError",
    "RssIconNotFoundError",
    "RssRepositorySyncError",
    # Exception handlers
    "rss_catalog_parse_error_handler",
    "rss_company_not_found_error_handler",
    "rss_feed_not_found_error_handler",
    "rss_feed_toggle_forbidden_error_handler",
    "rss_icon_not_found_error_handler",
    "rss_repository_sync_error_handler",
]
