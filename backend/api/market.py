from fastapi import APIRouter

from backend.api.schemas import QuoteOut
from backend.services.market_service import get_market_leaders

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/leaders", response_model=list[QuoteOut])
def read_market_leaders():
    """The curated leader list, ranked by live market cap.

    No error status here, deliberately. Failure is per-ticker and already reported
    on the entry that failed, so there is nothing this endpoint can fail with —
    returning a 502 because one of ten symbols was unreachable would throw away the
    nine that worked.
    """
    return get_market_leaders()
