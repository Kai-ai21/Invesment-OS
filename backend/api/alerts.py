from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.schemas import AlertOut
from backend.models.database import get_db
from backend.repositories import alert_repository

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(unread_only: bool = False, db: Session = Depends(get_db)):
    return alert_repository.list_alerts(db, unread_only=unread_only)
