from sqlalchemy.orm import Session

from app.clients.database import check_db_connection
from app.schemas.health import HealthRead


def get_health_status(db: Session) -> HealthRead:
    if check_db_connection(db):
        return HealthRead(status="ok", database="ok")
    return HealthRead(status="degraded", database="unavailable")
