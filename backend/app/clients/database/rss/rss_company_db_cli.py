from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rss import RssCompany


def get_company_by_id(db: Session, company_id: int) -> RssCompany | None:
    return db.execute(
        select(RssCompany).where(RssCompany.id == company_id)
    ).scalar_one_or_none()

def get_company_by_name(db: Session, company_name: str) -> RssCompany | None:
    return db.execute(
        select(RssCompany).where(RssCompany.name == company_name)
    ).scalar_one_or_none()

def get_or_create_company(db: Session, company_name: str) -> tuple[RssCompany, bool]:
    existing_company = get_company_by_name(db, company_name)
    if existing_company is not None:
        return existing_company, False

    new_company = RssCompany(name=company_name, enabled=True)
    db.add(new_company)
    db.flush()
    return new_company, True