from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.schemas import ResearchOut
from backend.models.database import get_db
from backend.services.research_service import ResearchUnavailableError, get_research

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/{ticker}", response_model=ResearchOut)
def read_research(ticker: str, db: Session = Depends(get_db)):
    """Profile plus a plain-language summary of the company's latest filing.

    SLOW on a cold cache — a filing fetch, two retrieval passes and one AI call, so
    10-20 seconds is normal. Cached per ticker for 24 hours afterwards.

    404 means no such ticker. 502 means every upstream failed. A filing that could
    not be read is NEITHER: it comes back 200 with the profile and
    `filing_summary_unavailable` set, because a page with the profile on it is
    useful and an error screen is not.
    """
    try:
        research = get_research(db, ticker)
    except ResearchUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if research is None:
        raise HTTPException(status_code=404, detail=f"No company found for {ticker}")
    return research
