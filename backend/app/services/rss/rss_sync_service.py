from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.clients.database import (
    delete_rss_companies_without_feeds,
    delete_company_feeds_not_in_urls,
    get_or_create_company,
    get_or_create_tags,
    get_rss_catalog_sync_state,
    link_company_to_feed,
    list_rss_company_ids_with_feeds,
    list_rss_feeds_by_urls,
    mark_rss_catalog_sync_failure,
    mark_rss_catalog_sync_success,
    upsert_feed,
)
from app.clients.networking.rss import (
    load_source_feeds_from_json,
    sync_rss_feeds_repository,
)
from app.domain.rss import normalize_source_feed_entry
from app.schemas.rss import RssRepositorySyncRead, RssSyncRead
from app.utils import (
    get_rss_feeds_repository_branch,
    get_rss_feeds_repository_path,
    get_rss_feeds_repository_url,
    list_files_on_dir_with_ext,
    normalize_country,
)

logger = logging.getLogger(__name__)
_CATALOG_DIR = "json"


@dataclass(slots=True)
class _CatalogReconcileResult:
    files_processed: int = 0
    companies_removed: int = 0
    feeds_removed: int = 0


def sync_rss_catalog(db: Session, force: bool = False) -> RssSyncRead:
    repository_path = get_rss_feeds_repository_path()
    repository_sync = sync_rss_feeds_repository(
        repository_url=get_rss_feeds_repository_url(),
        repository_path=repository_path,
        branch=get_rss_feeds_repository_branch(),
    )
    _log_repository_sync_action(repository_sync)

    sync_state = get_rss_catalog_sync_state(db)
    last_applied_revision = (
        sync_state.last_applied_revision
        if sync_state is not None
        else None
    )
    should_reconcile = force or repository_sync.current_revision != last_applied_revision

    if not should_reconcile:
        return _build_sync_response(
            repository_sync,
            mode="noop",
            applied_from_revision=last_applied_revision,
            reconcile_result=_CatalogReconcileResult(),
        )

    try:
        reconcile_result = _reconcile_rss_catalog(
            db,
            repository_path=repository_path,
        )
        mark_rss_catalog_sync_success(
            db,
            current_revision=repository_sync.current_revision,
        )
        db.commit()
    except Exception as exception:
        db.rollback()
        _persist_catalog_sync_failure(
            db,
            current_revision=repository_sync.current_revision,
            error_message=str(exception),
        )
        raise

    return _build_sync_response(
        repository_sync,
        mode="full_reconcile",
        applied_from_revision=last_applied_revision,
        reconcile_result=reconcile_result,
    )


def _reconcile_rss_catalog(
    db: Session,
    *,
    repository_path: Path,
) -> _CatalogReconcileResult:
    result = _CatalogReconcileResult()
    catalog_repository_path = repository_path / _CATALOG_DIR
    relative_catalog_paths = (
        sorted(
            list_files_on_dir_with_ext(
                repository_path=catalog_repository_path,
                file_extension=".json",
            )
        )
        if catalog_repository_path.exists()
        else []
    )

    seen_company_ids: set[int] = set()

    for relative_catalog_path in relative_catalog_paths:
        company_id, feeds_removed = _sync_catalog_file(
            db,
            catalog_repository_path=catalog_repository_path,
            relative_json_file_path=relative_catalog_path,
        )
        seen_company_ids.add(company_id)
        result.files_processed += 1
        result.feeds_removed += feeds_removed

    _flush_pending_catalog_changes(db)
    for company_id in list_rss_company_ids_with_feeds(db):
        if company_id in seen_company_ids:
            continue
        result.feeds_removed += delete_company_feeds_not_in_urls(
            db,
            company_id=company_id,
            expected_urls=set(),
        )

    _flush_pending_catalog_changes(db)
    result.companies_removed = delete_rss_companies_without_feeds(db)
    return result


def _sync_catalog_file(
    db: Session,
    *,
    catalog_repository_path: Path,
    relative_json_file_path: str,
) -> tuple[int, int]:
    catalog_file_path = catalog_repository_path / relative_json_file_path
    catalog = load_source_feeds_from_json(catalog_file_path)
    company_fetchprotection = max(0, min(2, catalog.fetchprotection))
    company, _created = get_or_create_company(
        db,
        company_name=catalog.company.strip(),
        host=catalog.host,
        icon_url=(catalog.img.strip() if catalog.img else None),
        country=normalize_country(catalog.country),
        language=normalize_country(catalog.language),
        fetchprotection=company_fetchprotection,
    )
    existing_feeds_by_url = list_rss_feeds_by_urls(
        db,
        [feed.url for feed in catalog.feeds],
    )
    expected_urls: set[str] = set()

    for source_feed in catalog.feeds:
        payload = normalize_source_feed_entry(
            source_feed,
            default_fetchprotection=company_fetchprotection,
        )
        expected_urls.add(payload.url)
        tags, _created_tags = get_or_create_tags(db, payload.tags)
        feed, _created_feed = upsert_feed(
            db,
            payload=payload,
            tags=tags,
            existing_feed=existing_feeds_by_url.get(payload.url),
        )
        link_company_to_feed(
            db,
            company_id=company.id,
            feed_id=feed.id,
        )

    _flush_pending_catalog_changes(db)
    feeds_removed = delete_company_feeds_not_in_urls(
        db,
        company_id=company.id,
        expected_urls=expected_urls,
    )
    return company.id, feeds_removed


def _flush_pending_catalog_changes(db: Session) -> None:
    # The backend session runs with autoflush disabled, so cleanup queries must
    # explicitly flush pending feed/company links before they inspect the DB.
    db.flush()


def _persist_catalog_sync_failure(
    db: Session,
    *,
    current_revision: str | None,
    error_message: str,
) -> None:
    try:
        mark_rss_catalog_sync_failure(
            db,
            current_revision=current_revision,
            error_message=error_message,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("rss_sync - unable to persist sync failure state")


def _build_sync_response(
    repository_sync: RssRepositorySyncRead,
    *,
    mode: str,
    applied_from_revision: str | None,
    reconcile_result: _CatalogReconcileResult,
) -> RssSyncRead:
    return RssSyncRead(
        repository_action=repository_sync.action,
        mode=mode,
        current_revision=repository_sync.current_revision,
        applied_from_revision=applied_from_revision,
        files_processed=reconcile_result.files_processed,
        companies_removed=reconcile_result.companies_removed,
        feeds_removed=reconcile_result.feeds_removed,
    )


def _log_repository_sync_action(repository_sync: RssRepositorySyncRead) -> None:
    if repository_sync.action == "up_to_date":
        logger.info("rss_sync - repository up to date")
        return

    if repository_sync.action == "cloned":
        logger.info("rss_sync - repository cloned")
        return

    logger.info("rss_sync - repository updated")
