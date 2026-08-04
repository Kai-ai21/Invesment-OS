from fastapi import APIRouter, Depends, HTTPException, Query

from backend.adapters.yfinance_price_source import PriceError
from backend.api.deps import get_current_user
from backend.api.schemas import PriceHistoryOut, PricePointOut
from backend.models.user import User
from backend.services.price_service import get_history, get_price

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/{ticker}", response_model=PricePointOut)
def read_price(ticker: str, user: User = Depends(get_current_user)):
    """The latest price for a ticker.

    404 when the ticker is unknown, 502 when the upstream is unavailable — the two are
    genuinely different, and collapsing them would tell the user their ticker is wrong
    when the market data provider is simply down.
    """
    try:
        price = get_price(ticker)
    except PriceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if price is None:
        raise HTTPException(status_code=404, detail=f"No price data for {ticker}")
    return price


@router.get("/{ticker}/history", response_model=PriceHistoryOut)
def read_price_history(
    ticker: str,
    days: int = Query(default=365, ge=1, le=1825),
    user: User = Depends(get_current_user),
):
    try:
        points = get_history(ticker, days=days)
    except PriceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if not points:
        raise HTTPException(status_code=404, detail=f"No price history for {ticker}")
    return PriceHistoryOut(ticker=ticker.strip().upper(), points=points)
