class WorkerError(Exception):
    """Base worker exception."""


class WorkerAuthenticationError(WorkerError):
    """Raised when worker authentication to backend fails."""


class WorkerQueueError(WorkerError):
    """Raised when queue operations fail."""
