from sqlalchemy import text
from sqlalchemy.orm import Session


def check_db_connection(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
