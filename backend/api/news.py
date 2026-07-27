from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.schemas import NewsItemOut
from backend.models.database import get_db
from backend.services.news_service import get_news_for_all_theses

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=list[NewsItemOut])
def list_news(
    limit_per_ticker: int = Query(default=5, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Headlines across every ticker the user holds a thesis on, newest first.

    Returns [] when the user has no theses. Individual feed failures are isolated in
    the service, so a dead feed drops that ticker rather than failing the request.
    """
    return get_news_for_all_theses(db, limit_per_ticker=limit_per_ticker)
