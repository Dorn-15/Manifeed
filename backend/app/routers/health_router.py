from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.health_schema import HealthRead
from app.services.health_service import get_health_status
from database import get_db_session

health_router = APIRouter(prefix="/health", tags=["health"])


@health_router.get("/", response_model=HealthRead)
def read_health(db: Session = Depends(get_db_session)) -> HealthRead:
    return get_health_status(db)
