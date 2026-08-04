from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.api.schemas import (
    HoldingCreateRequest,
    HoldingUpdateRequest,
    PortfolioOut,
)
from backend.api.dependencies import current_user_id
from backend.models.database import get_db
from backend.repositories import holding_repository
from backend.services.portfolio_service import get_portfolio

router = APIRouter(prefix="/holdings", tags=["holdings"])


@router.get("", response_model=PortfolioOut)
def read_portfolio(
    db: Session = Depends(get_db), user_id: str = Depends(current_user_id)
):
    """The portfolio: every holding with its computed values, plus totals.

    Note there is no 502 here, unlike /prices. A price failure is per-holding and
    already reported on the row that failed — failing the whole request would throw
    away nine good rows because of one bad ticker.
    """
    return get_portfolio(db, user_id)


@router.post("", response_model=PortfolioOut, status_code=201)
def create_holding(
    body: HoldingCreateRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """Add a holding. Invalid input is rejected by the schema as a 422.

    Returns the whole portfolio rather than the one row, because adding a position
    changes every OTHER row's allocation percentage — sending back just the new
    holding would leave the client displaying stale percentages beside it.
    """
    holding_repository.create_holding(
        db,
        user_id=user_id,
        ticker=body.ticker,  # already normalised to uppercase by the schema
        shares=body.shares,
        average_cost=body.average_cost,
        purchased_at=body.purchased_at,
        note=body.note,
    )
    return get_portfolio(db, user_id)


@router.patch("/{holding_id}", response_model=PortfolioOut)
def update_holding(
    holding_id: str,
    body: HoldingUpdateRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    updated = holding_repository.update_holding(
        db,
        holding_id,
        user_id,
        shares=body.shares,
        average_cost=body.average_cost,
        note=body.note,
        # Which keys the client actually sent, so an omitted `note` is left alone and
        # an explicit null clears it.
        fields_set=body.model_fields_set,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Holding not found")
    return get_portfolio(db, user_id)


@router.delete("/{holding_id}", status_code=204)
def delete_holding(
    holding_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    if not holding_repository.delete_holding(db, holding_id, user_id):
        raise HTTPException(status_code=404, detail="Holding not found")
    return Response(status_code=204)
