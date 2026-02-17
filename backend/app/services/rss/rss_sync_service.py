from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.clients.database.rss import (
    delete_company_feeds_not_in_urls,
    get_company_by_name,
    get_or_create_company,
    get_or_create_tags,
    list_rss_feeds_by_urls,
    upsert_feed,
)
from app.clients.networking.rss import (
    load_source_feeds_from_json,
    sync_rss_feeds_repository,
)
from app.domain.rss import normalize_source_feed_entry
from app.errors.rss import RssCatalogParseError
from app.schemas.rss import (
    RssRepositorySyncRead,
    RssSyncRead,
)
from app.utils import (
    get_rss_feeds_repository_branch,
    get_rss_feeds_repository_url,
    resolve_rss_feeds_repository_path,
    normalize_name_from_filename,
)

logger = logging.getLogger(__name__)


def sync_rss_catalog(db: Session) -> RssSyncRead:
    repository_url = get_rss_feeds_repository_url()
    repository_branch = get_rss_feeds_repository_branch()
    repository_path = resolve_rss_feeds_repository_path()

    repository_sync = sync_rss_feeds_repository(
        repository_url=repository_url,
        repository_path=repository_path,
        branch=repository_branch,
    )
    _log_repository_sync_action(repository_sync)

    total_stats = _SyncStats()
    try:
        for relative_json_file_path in repository_sync.changed_files:
            total_stats = _merge_sync_stats(
                current_stats=total_stats,
                next_stats=_sync_catalog_file(
                    db=db,
                    repository_path=repository_path,
                    relative_json_file_path=relative_json_file_path,
                ),
            )

        if repository_sync.changed_files:
            db.commit()
    except Exception:
        db.rollback()
        raise

    return _build_sync_response(repository_sync, total_stats)


def _sync_catalog_file(
    db: Session,
    repository_path: Path,
    relative_json_file_path: str,
) -> _SyncStats:
    catalog_file_path = repository_path / relative_json_file_path
    company_name = _extract_company_name(relative_json_file_path)
    stats = _SyncStats(processed_files=1)

    if not catalog_file_path.exists():
        existing_company = get_company_by_name(db, company_name)
        if existing_company is None:
            return stats

        stats.deleted_feeds = delete_company_feeds_not_in_urls(
            db=db,
            company_id=existing_company.id,
            expected_urls=set(),
        )
        return stats

    company, created_company = get_or_create_company(db, company_name)
    if created_company:
        stats.created_companies += 1

    source_feeds = load_source_feeds_from_json(catalog_file_path)
    upsert_payloads = [
        normalize_source_feed_entry(source_feed)
        for source_feed in source_feeds
    ]
    expected_urls = {upsert_payload.url for upsert_payload in upsert_payloads}
    existing_feeds_by_url = list_rss_feeds_by_urls(
        db=db,
        urls=[upsert_payload.url for upsert_payload in upsert_payloads],
    )

    for upsert_payload in upsert_payloads:
        tags, created_tags = get_or_create_tags(db, upsert_payload.tags)
        stats.created_tags += created_tags

        feed, created_feed = upsert_feed(
            db=db,
            company=company,
            payload=upsert_payload,
            tags=tags,
            existing_feed=existing_feeds_by_url.get(upsert_payload.url),
        )
        existing_feeds_by_url[upsert_payload.url] = feed
        stats.processed_feeds += 1
        if created_feed:
            stats.created_feeds += 1
        else:
            stats.updated_feeds += 1

    stats.deleted_feeds = delete_company_feeds_not_in_urls(
        db=db,
        company_id=company.id,
        expected_urls=expected_urls,
    )
    return stats


def _build_sync_response(
    repository_sync: RssRepositorySyncRead,
    total_stats: "_SyncStats",
) -> RssSyncRead:
    return RssSyncRead(
        repository_action=  repository_sync.action,
        processed_files=    total_stats.processed_files,
        processed_feeds=    total_stats.processed_feeds,
        created_companies=  total_stats.created_companies,
        created_tags=       total_stats.created_tags,
        created_feeds=      total_stats.created_feeds,
        updated_feeds=      total_stats.updated_feeds,
        deleted_feeds=      total_stats.deleted_feeds,
    )


def _log_repository_sync_action(repository_sync: RssRepositorySyncRead) -> None:
    if repository_sync.action == "up_to_date":
        logger.info("rss_sync - repository up to date")
        return

    if repository_sync.action == "cloned":
        logger.info("rss_sync - repository cloned")
        return

    logger.info("rss_sync - repository updated")


def _extract_company_name(relative_json_file_path: str) -> str:
    try:
        return normalize_name_from_filename(relative_json_file_path)
    except ValueError as exception:
        raise RssCatalogParseError(str(exception)) from exception


def _merge_sync_stats(current_stats: "_SyncStats", next_stats: "_SyncStats") -> "_SyncStats":
    return _SyncStats(
        processed_files=    current_stats.processed_files   + next_stats.processed_files,
        processed_feeds=    current_stats.processed_feeds   + next_stats.processed_feeds,
        created_companies=  current_stats.created_companies + next_stats.created_companies,
        created_tags=       current_stats.created_tags      + next_stats.created_tags,
        created_feeds=      current_stats.created_feeds     + next_stats.created_feeds,
        updated_feeds=      current_stats.updated_feeds     + next_stats.updated_feeds,
        deleted_feeds=      current_stats.deleted_feeds     + next_stats.deleted_feeds,
    )


@dataclass
class _SyncStats:
    processed_files:    int = 0
    processed_feeds:    int = 0
    created_companies:  int = 0
    created_tags:       int = 0
    created_feeds:      int = 0
    updated_feeds:      int = 0
    deleted_feeds:      int = 0
