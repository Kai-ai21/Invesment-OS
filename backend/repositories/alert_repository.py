from sqlalchemy.orm import Session, joinedload

from backend.models.alert import Alert
from backend.models.thesis import Thesis
from backend.repositories import thesis_repository


def _owned(query, user_id: str):
    """Constrain an Alert query to one user, through its thesis.

    Alerts carry no user_id of their own — they belong to whoever owns the thesis
    whose status changed — so every read joins.
    """
    return query.join(Thesis, Alert.thesis_id == Thesis.id).filter(
        Thesis.user_id == user_id
    )


def create_alert(
    db: Session,
    *,
    thesis_id: str,
    user_id: str,
    prev_status: str,
    new_status: str,
    summary: str,
) -> Alert | None:
    """Record a status transition. None when the thesis is not this user's."""
    if thesis_repository.get_thesis(db, thesis_id, user_id) is None:
        return None

    alert = Alert(
        thesis_id=thesis_id, prev_status=prev_status, new_status=new_status, summary=summary
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def list_alerts(db: Session, user_id: str, unread_only: bool = False) -> list[Alert]:
    # Eager-load the thesis so reading `alert.ticker` on each row is one query rather
    # than N. The joinedload is for LOADING; the join in _owned is for FILTERING —
    # separate concerns, and both are needed.
    query = _owned(db.query(Alert), user_id).options(joinedload(Alert.thesis))
    if unread_only:
        query = query.filter(Alert.is_read.is_(False))
    return query.order_by(Alert.created_at.desc()).all()


def list_alerts_for_thesis(db: Session, thesis_id: str, user_id: str) -> list[Alert]:
    """Every alert on one thesis, oldest first — the chart's status-change track.

    Added in A2 to replace the chart service's "load every alert in the database, then
    filter in Python" loop, which was both unscoped and O(all alerts in the table) to
    draw one thesis's timeline.
    """
    return (
        _owned(db.query(Alert), user_id)
        .filter(Alert.thesis_id == thesis_id)
        .order_by(Alert.created_at.asc())
        .all()
    )


def get_alert(db: Session, alert_id: str, user_id: str) -> Alert | None:
    return (
        _owned(db.query(Alert), user_id)
        .options(joinedload(Alert.thesis))
        .filter(Alert.id == alert_id)
        .first()
    )


def mark_alert_read(db: Session, alert_id: str, user_id: str) -> Alert | None:
    """Returns None when no such alert exists FOR THIS USER, so the caller can 404."""
    alert = get_alert(db, alert_id, user_id)
    if alert is None:
        return None

    alert.is_read = True
    db.commit()
    db.refresh(alert)
    return alert
