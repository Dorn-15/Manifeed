class DBManagerError(Exception):
    """Base db-manager exception."""


class DBManagerQueueError(DBManagerError):
    """Raised when queue operations fail."""
