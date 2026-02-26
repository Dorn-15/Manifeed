from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.clients.database.rss import (
    delete_company_feeds_not_in_urls,
    get_company_by_name,
    get_or_create_company,
    get_or_create_tags,
    link_company_to_feed,
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
    normalize_name_from_filename,
    normalize_country,
    get_rss_feeds_repository_path,
)

logger = logging.getLogger(__name__)


def sync_rss_catalog(db: Session, force: bool = False) -> RssSyncRead:
    repository_path = get_rss_feeds_repository_path()
    
    repository_sync = sync_rss_feeds_repository(
        repository_url=get_rss_feeds_repository_url(),
        repository_path=repository_path,
        branch=get_rss_feeds_repository_branch(),
        force=force,
    )
    _log_repository_sync_action(repository_sync)

    if not repository_sync.changed_files:
        return _build_sync_response(repository_sync)

    try:
        for relative_json_file_path in repository_sync.changed_files:
            _sync_catalog_file(
                db=db,
                repository_path=repository_path,
                relative_json_file_path=relative_json_file_path,
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return _build_sync_response(repository_sync)


def _sync_catalog_file(
    db: Session,
    repository_path: Path,
    relative_json_file_path: str,
) -> None:
    catalog_file_path = repository_path / relative_json_file_path
    fallback_company_name = _extract_company_name(relative_json_file_path)

    if not catalog_file_path.exists():
        existing_company = get_company_by_name(db, fallback_company_name)
        if existing_company:
            delete_company_feeds_not_in_urls(
                db=db,
                company_id=existing_company.id,
                expected_urls=set(),
            )
        return

    catalog = load_source_feeds_from_json(catalog_file_path)
    company, _ = get_or_create_company(
        db,
        company_name=catalog.company.strip() or fallback_company_name,
        host=catalog.host,
        icon_url=catalog.img.strip(),
        country=normalize_country(catalog.country),
        language=normalize_country(catalog.language),
        fetchprotection=max(0, min(2, catalog.fetchprotection)),
    )

    upsert_payloads = [
        normalize_source_feed_entry(
            source_feed,
            default_fetchprotection=company.fetchprotection,
        )
        for source_feed in catalog.feeds
    ]
    expected_urls = {upsert_payload.url for upsert_payload in upsert_payloads}
    existing_feeds_by_url = list_rss_feeds_by_urls(
        db=db,
        urls=[upsert_payload.url for upsert_payload in upsert_payloads],
    )

    for upsert_payload in upsert_payloads:
        tags, _ = get_or_create_tags(db, upsert_payload.tags)

        feed, _ = upsert_feed(
            db=db,
            payload=upsert_payload,
            tags=tags,
            existing_feed=existing_feeds_by_url.get(upsert_payload.url),
        )
        existing_feeds_by_url[upsert_payload.url] = feed
        link_company_to_feed(db, company_id=company.id, feed_id=feed.id)

    delete_company_feeds_not_in_urls(
        db=db,
        company_id=company.id,
        expected_urls=expected_urls,
    )


def _build_sync_response(repository_sync: RssRepositorySyncRead) -> RssSyncRead:
    return RssSyncRead(
        repository_action=repository_sync.action,
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
