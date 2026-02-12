class RssSyncError(Exception):
    """Base exception for RSS sync workflow errors."""


class RssRepositorySyncError(RssSyncError):
    """Raised when git repository synchronization fails."""


class RssCatalogParseError(RssSyncError):
    """Raised when RSS source JSON payload parsing fails."""


class RssIconNotFoundError(RssSyncError):
    """Raised when an RSS icon cannot be resolved from the local repository."""


class RssFeedNotFoundError(RssSyncError):
    """Raised when an RSS feed cannot be found."""


class RssCompanyNotFoundError(RssSyncError):
    """Raised when an RSS company cannot be found."""


class RssFeedToggleForbiddenError(RssSyncError):
    """Raised when RSS feed toggle rules are violated."""
