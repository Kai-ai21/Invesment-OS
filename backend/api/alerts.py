from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.api.schemas import AlertOut
from backend.models.database import get_db
from backend.models.user import User
from backend.repositories import alert_repository

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return alert_repository.list_alerts(db, user.id, unread_only=unread_only)


@router.patch("/{alert_id}/read", response_model=AlertOut)
def mark_read(
    alert_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """404 — not 403 — when the alert belongs to somebody else.

    The repository returns None for "no such alert" and for "not yours" alike, so
    this endpoint could not tell them apart even if it wanted to. That is the point:
    a 403 here would confirm that the id names a real alert.
    """
    alert = alert_repository.mark_alert_read(db, alert_id, user.id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert
