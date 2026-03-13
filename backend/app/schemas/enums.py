from __future__ import annotations

from enum import StrEnum


class WorkerJobKind(StrEnum):
    RSS_SCRAPE_CHECK = "rss_scrape_check"
    RSS_SCRAPE_INGEST = "rss_scrape_ingest"
    SOURCE_EMBEDDING = "source_embedding"


class WorkerJobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class WorkerTaskStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkerTaskOutcome(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


class WorkerKind(StrEnum):
    RSS_SCRAPPER = "rss_scrapper"
    SOURCE_EMBEDDING = "source_embedding"


class RssFeedRuntimeStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    NOT_MODIFIED = "not_modified"
    ERROR = "error"


class RssScrapeItemStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    NOT_MODIFIED = "not_modified"
    ERROR = "error"


class EmbeddingItemStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    ERROR = "error"
