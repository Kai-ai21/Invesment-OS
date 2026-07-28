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


def get_holding(db: Session, holding_id: str) -> Holding | None:
    return db.get(Holding, holding_id)


def update_holding(
    db: Session,
    holding_id: str,
    *,
    shares: float | None = None,
    average_cost: float | None = None,
    note: str | None = None,
    fields_set: set[str] | None = None,
) -> Holding | None:
    """Partial update. Returns None when no such holding, so the caller can 404.

    `fields_set` carries which keys the request actually SUPPLIED, because None is
    ambiguous on its own: omitting `note` must leave it alone, while sending an
    explicit null must clear it. Without that distinction a user could never delete a
    note they had written.
    """
    holding = get_holding(db, holding_id)
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


def delete_holding(db: Session, holding_id: str) -> bool:
    """True when a row was removed, False when there was nothing to remove."""
    holding = get_holding(db, holding_id)
    if holding is None:
        return False

    db.delete(holding)
    db.commit()
    return True
