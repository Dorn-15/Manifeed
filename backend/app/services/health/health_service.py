from sqlalchemy.orm import Session

from app.clients.database.health import check_db_connection
from app.schemas.health import HealthRead


def get_health_status(db: Session) -> HealthRead:
    database_ok = check_db_connection(db)    
    if not database_ok:
        return HealthRead(status="degraded", database="unavailable")
    
    return HealthRead(status="ok", database="ok")
