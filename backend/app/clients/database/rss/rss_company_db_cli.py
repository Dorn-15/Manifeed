from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rss import RssCompany
from app.utils import normalize_country, normalize_host


def get_company_by_id(db: Session, company_id: int) -> RssCompany | None:
    return db.execute(
        select(RssCompany).where(RssCompany.id == company_id)
    ).scalar_one_or_none()


def get_company_by_name(db: Session, company_name: str) -> RssCompany | None:
    return db.execute(
        select(RssCompany).where(RssCompany.name == company_name)
    ).scalar_one_or_none()


def get_or_create_company(
    db: Session,
    company_name: str,
    *,
    host: str | None = None,
    icon_url: str | None,
    country: str | None,
    language: str | None,
    fetchprotection: int,
) -> tuple[RssCompany, bool]:
    existing_company = get_company_by_name(db, company_name)
    if existing_company is not None:
        _update_company_metadata(
            existing_company,
            host=host,
            icon_url=icon_url,
            country=country,
            language=language,
            fetchprotection=fetchprotection,
        )
        return existing_company, False

    new_company = RssCompany(
        name=company_name,
        host=normalize_host(host),
        icon_url=icon_url,
        country=normalize_country(country),
        language=normalize_country(language),
        fetchprotection=max(0, min(2, fetchprotection)),
        enabled=True,
    )
    db.add(new_company)
    db.flush()
    return new_company, True


def _update_company_metadata(
    company: RssCompany,
    *,
    host: str | None = None,
    icon_url: str | None,
    country: str | None,
    language: str | None,
    fetchprotection: int,
) -> None:
    company.host = normalize_host(host)
    company.icon_url = (
        icon_url.strip()
        if isinstance(icon_url, str) and icon_url.strip()
        else None
    )
    company.country = normalize_country(country)
    company.language = normalize_country(language)
    company.fetchprotection = max(0, min(2, fetchprotection))
