from sqlalchemy.orm import Session, joinedload

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
    # Eager-load the thesis so reading `alert.ticker` on each row is one query
    # rather than N.
    query = db.query(Alert).options(joinedload(Alert.thesis))
    if unread_only:
        query = query.filter(Alert.is_read.is_(False))
    return query.order_by(Alert.created_at.desc()).all()


def get_alert(db: Session, alert_id: str) -> Alert | None:
    return (
        db.query(Alert)
        .options(joinedload(Alert.thesis))
        .filter(Alert.id == alert_id)
        .first()
    )


def mark_alert_read(db: Session, alert_id: str) -> Alert | None:
    """Returns None when no such alert exists, so the caller can 404."""
    alert = get_alert(db, alert_id)
    if alert is None:
        return None

    alert.is_read = True
    db.commit()
    db.refresh(alert)
    return alert
