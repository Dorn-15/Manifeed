from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rss import RssCompany, RssFeed, RssTag
from app.schemas.rss import RssFeedUpsertSchema


def get_company_by_name(db: Session, company_name: str) -> RssCompany | None:
    return db.execute(
        select(RssCompany).where(RssCompany.name == company_name)
    ).scalar_one_or_none()


def get_or_create_company(db: Session, company_name: str) -> tuple[RssCompany, bool]:
    existing_company = get_company_by_name(db, company_name)
    if existing_company is not None:
        return existing_company, False

    new_company = RssCompany(name=company_name)
    db.add(new_company)
    db.flush()
    return new_company, True


def get_or_create_tags(
    db: Session,
    tag_names: Sequence[str],
) -> tuple[list[RssTag], int]:
    unique_tag_names = _deduplicate_tag_names(tag_names)
    if not unique_tag_names:
        return [], 0

    existing_tags = db.execute(
        select(RssTag).where(RssTag.name.in_(unique_tag_names))
    ).scalars().all()
    tags_by_name: dict[str, RssTag] = {tag.name: tag for tag in existing_tags}

    created_tags_count = 0
    for tag_name in unique_tag_names:
        if tag_name in tags_by_name:
            continue
        new_tag = RssTag(name=tag_name)
        db.add(new_tag)
        db.flush()
        tags_by_name[tag_name] = new_tag
        created_tags_count += 1

    tags_in_input_order = [tags_by_name[tag_name] for tag_name in unique_tag_names]
    return tags_in_input_order, created_tags_count


def upsert_feed(
    db: Session,
    company: RssCompany,
    payload: RssFeedUpsertSchema,
    tags: Sequence[RssTag],
) -> tuple[RssFeed, bool]:
    existing_feed = db.execute(
        select(RssFeed).where(RssFeed.url == payload.url)
    ).scalar_one_or_none()

    if existing_feed is None:
        new_feed = RssFeed(
            url=payload.url,
            company=company,
            section=payload.section,
            enabled=payload.enabled,
            status="unchecked",
            trust_score=payload.trust_score,
            language=payload.language,
            icon_url=payload.icon_url,
            parsing_config=payload.parsing_config,
            tags=list(tags),
        )
        db.add(new_feed)
        db.flush()
        return new_feed, True

    existing_feed.company = company
    existing_feed.section = payload.section
    existing_feed.enabled = payload.enabled
    existing_feed.trust_score = payload.trust_score
    existing_feed.language = payload.language
    existing_feed.icon_url = payload.icon_url
    existing_feed.parsing_config = payload.parsing_config
    existing_feed.tags = list(tags)
    db.flush()
    return existing_feed, False


def delete_company_feeds_not_in_urls(
    db: Session,
    company_id: int,
    expected_urls: set[str],
) -> int:
    """Delete feeds that are not in the expected URLs."""
    feeds_query = select(RssFeed).where(RssFeed.company_id == company_id)
    if expected_urls:
        feeds_query = feeds_query.where(~RssFeed.url.in_(expected_urls))

    stale_feeds = db.execute(feeds_query).scalars().all()
    for stale_feed in stale_feeds:
        db.delete(stale_feed)

    if stale_feeds:
        db.flush()
    return len(stale_feeds)


def _deduplicate_tag_names(tag_names: Sequence[str]) -> list[str]:
    unique_names: list[str] = []
    seen_names: set[str] = set()

    for tag_name in tag_names:
        cleaned_name = tag_name.strip()
        if not cleaned_name or cleaned_name in seen_names:
            continue
        seen_names.add(cleaned_name)
        unique_names.append(cleaned_name)

    return unique_names
