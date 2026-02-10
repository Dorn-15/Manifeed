from sqlalchemy.orm import Session

from app.clients.database.health import check_db_connection
from app.schemas.health import HealthRead


def get_health_status(db: Session) -> HealthRead:
    database_ok = check_db_connection(db)
    return HealthRead(
        status="ok" if database_ok else "degraded",
        database="ok" if database_ok else "unavailable",
    )
