from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rss import RssTag

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

    missing_tag_names = [
        tag_name for tag_name in unique_tag_names if tag_name not in tags_by_name
    ]
    created_tags_count = len(missing_tag_names)
    if missing_tag_names:
        new_tags = [RssTag(name=tag_name) for tag_name in missing_tag_names]
        db.add_all(new_tags)
        db.flush()
        for new_tag in new_tags:
            tags_by_name[new_tag.name] = new_tag

    tags_in_input_order = [tags_by_name[tag_name] for tag_name in unique_tag_names]
    return tags_in_input_order, created_tags_count

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