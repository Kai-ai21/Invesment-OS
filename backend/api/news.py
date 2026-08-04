from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.adapters.rss_news_source import NewsError
from backend.api.deps import get_current_user
from backend.api.schemas import NewsItemOut
from backend.models.database import get_db
from backend.models.user import User
from backend.services.news_service import get_news_for_all_theses, get_news_for_ticker

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=list[NewsItemOut])
def list_news(
    limit_per_ticker: int = Query(default=5, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Headlines across every ticker the user holds a thesis on, newest first.

    Returns [] when the user has no theses. Individual feed failures are isolated in
    the service, so a dead feed drops that ticker rather than failing the request.
    """
    return get_news_for_all_theses(db, user.id, limit_per_ticker=limit_per_ticker)


@router.get("/{ticker}", response_model=list[NewsItemOut])
def list_news_for_ticker(
    ticker: str,
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
):
    """Headlines for one ticker, newest first.

    No `db`: this reads a feed, not the user's theses — so it answers for any symbol,
    including ones they have never written about.

    AN EMPTY LIST IS A REAL ANSWER. A symbol nobody published about this week is not
    an error, and the pages rendering this show "no recent news" for it. 404 is
    reserved for input that could not name a company at all.

    502 when the feed itself failed, matching /prices: "we could not look" must never
    arrive looking like "there is nothing to see".
    """
    try:
        headlines = get_news_for_ticker(ticker, limit=limit)
    except NewsError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if headlines is None:
        raise HTTPException(status_code=404, detail=f"Not a ticker symbol: {ticker!r}")
    return headlines
