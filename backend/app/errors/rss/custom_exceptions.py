class RssSyncError(Exception):
    """Base exception for RSS sync workflow errors."""


class RssRepositorySyncError(RssSyncError):
    """Raised when git repository synchronization fails."""


class RssCatalogParseError(RssSyncError):
    """Raised when RSS source JSON payload parsing fails."""


class RssIconNotFoundError(RssSyncError):
    """Raised when an RSS icon cannot be resolved from the local repository."""
