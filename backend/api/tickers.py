from fastapi import APIRouter, Depends, HTTPException, Query

from backend.adapters.edgar_source import EdgarError
from backend.api.deps import get_current_user
from backend.api.schemas import TickerMatchOut
from backend.models.user import User
from backend.services.ticker_service import search_tickers

router = APIRouter(prefix="/tickers", tags=["tickers"])


@router.get("/search", response_model=list[TickerMatchOut])
def search(
    q: str = Query(default="", description="Partial ticker or company name."),
    limit: int = Query(default=8, ge=1, le=25),
    user: User = Depends(get_current_user),
):
    """Ticker suggestions from the SEC's company list.

    An empty result is a normal answer, not an error: a short query, or a symbol
    the SEC does not list. The frontend says "no match, you can still submit"
    rather than blocking, because this list is comprehensive but not a gate.

    502 only when the SEC map itself cannot be fetched — and even then the input
    stays usable as plain text.
    """
    try:
        return search_tickers(q, limit=limit)
    except EdgarError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
