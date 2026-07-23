from sqlalchemy.orm import Session

from backend.models.alert import Alert


def create_alert(
    db: Session, *, thesis_id: str, prev_status: str, new_status: str, summary: str
) -> Alert:
    alert = Alert(
        thesis_id=thesis_id, prev_status=prev_status, new_status=new_status, summary=summary
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def list_alerts(db: Session, unread_only: bool = False) -> list[Alert]:
    query = db.query(Alert)
    if unread_only:
        query = query.filter(Alert.is_read.is_(False))
    return query.order_by(Alert.created_at.desc()).all()
