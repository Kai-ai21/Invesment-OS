from datetime import date

from sqlalchemy.orm import Session

from backend.models.holding import Holding


def create_holding(
    db: Session,
    *,
    user_id: str,
    ticker: str,
    shares: float,
    average_cost: float,
    purchased_at: date | None = None,
    note: str | None = None,
) -> Holding:
    holding = Holding(
        user_id=user_id,
        ticker=ticker,
        shares=shares,
        average_cost=average_cost,
        purchased_at=purchased_at,
        note=note,
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding


def list_holdings_for_user(db: Session, user_id: str) -> list[Holding]:
    # Ticker order, not creation order: a portfolio is read as a table to scan, and a
    # stable alphabetical list means a row does not move when another is edited.
    return (
        db.query(Holding)
        .filter(Holding.user_id == user_id)
        .order_by(Holding.ticker.asc(), Holding.created_at.asc())
        .all()
    )


def get_holding(db: Session, holding_id: str, user_id: str) -> Holding | None:
    """One holding, ONLY if this user owns it.

    ⚠️ NOT `db.get(Holding, holding_id)`, which is what this was. Holdings carry a
    user_id directly, so this is the easiest scope in the codebase to add and was
    still missing — and update_holding and delete_holding both routed through it,
    which put a stranger's position one guessed uuid away from being edited or
    deleted.
    """
    return (
        db.query(Holding)
        .filter(Holding.id == holding_id, Holding.user_id == user_id)
        .first()
    )


def update_holding(
    db: Session,
    holding_id: str,
    user_id: str,
    *,
    shares: float | None = None,
    average_cost: float | None = None,
    note: str | None = None,
    fields_set: set[str] | None = None,
) -> Holding | None:
    """Partial update. Returns None when this user has no such holding, so callers 404.

    `fields_set` carries which keys the request actually SUPPLIED, because None is
    ambiguous on its own: omitting `note` must leave it alone, while sending an
    explicit null must clear it. Without that distinction a user could never delete a
    note they had written.
    """
    holding = get_holding(db, holding_id, user_id)
    if holding is None:
        return None

    supplied = fields_set if fields_set is not None else set()

    if shares is not None:
        holding.shares = shares
    if average_cost is not None:
        holding.average_cost = average_cost
    if "note" in supplied:
        holding.note = note

    db.commit()
    db.refresh(holding)
    return holding


def delete_holding(db: Session, holding_id: str, user_id: str) -> bool:
    """True when a row was removed, False when there was nothing of THIS USER'S to
    remove — which is also the answer for a holding that exists and is someone
    else's, so the endpoint 404s either way rather than confirming it is real."""
    holding = get_holding(db, holding_id, user_id)
    if holding is None:
        return False

    db.delete(holding)
    db.commit()
    return True
