from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.api.schemas import FilingOut, FilingSummariseRequest, FilingSummaryOut
from backend.models.database import get_db
from backend.models.user import User
from backend.services.filing_service import (
    FilingNotListedError,
    FilingSourceError,
    list_filings,
    summarise_filing,
)

router = APIRouter(prefix="/filings", tags=["filings"])


@router.get("/{ticker}", response_model=list[FilingOut])
def read_filings(
    ticker: str,
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
):
    """Recent 10-K, 10-Q and 8-K filings for one ticker, newest first.

    No `db`: this reads the SEC's index, not the user's theses, so it answers for any
    symbol — including ones they have never written about.

    AN EMPTY LIST IS A REAL ANSWER, and means a real company that has filed none of
    these three forms. 404 is reserved for a symbol the SEC does not list at all, and
    502 for the SEC being unreachable: "we could not look" must never arrive looking
    like "there is nothing to see".

    Cached server-side for six hours per ticker.
    """
    try:
        filings = list_filings(ticker, limit=limit)
    except FilingSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if filings is None:
        raise HTTPException(status_code=404, detail=f"No SEC filings found for {ticker}")
    return filings


@router.post("/summarise", response_model=FilingSummaryOut)
def summarise(
    request: FilingSummariseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """One filing, restated in plain language.

    ⚠️ READ-ONLY. This creates no evidence, moves no claim or thesis status, and
    writes nothing at all — see backend/services/filing_service.py. It is the reading
    half of the app; POST /theses/{id}/check is the verifying half, and they must
    never be confused.

    SLOW on a cold cache — a filing fetch, two retrieval passes and one AI call, so
    10-20 seconds is normal. Cached for 30 days afterwards, since a filing's contents
    are fixed the moment it is filed.

    404 means the ticker is unknown, or `url` is not one of the SEC's recent filings
    for it — the URL is checked against the SEC's own index before anything is
    fetched, so an arbitrary address is refused rather than retrieved. 502 means the
    SEC or the AI call failed.
    """
    try:
        summary = summarise_filing(db, request.ticker, request.url, user.id)
    except FilingNotListedError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FilingSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if summary is None:
        raise HTTPException(
            status_code=404, detail=f"No SEC filings found for {request.ticker}"
        )
    return summary
