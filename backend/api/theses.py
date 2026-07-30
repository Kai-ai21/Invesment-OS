from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.adapters.edgar_source import EdgarError
from backend.adapters.gemini_provider import GeminiProvider
from backend.api.schemas import (
    ChartDataOut,
    EnhanceReasoningOut,
    EnhanceReasoningRequest,
    CheckResultOut,
    DocumentSubmitRequest,
    EvidenceEventOut,
    PostMortemOut,
    ThesisCreateRequest,
    ThesisOut,
)
from backend.domain.status import BROKEN_CLAIM_STATUS
from backend.models.database import get_db
from backend.repositories import (
    evidence_repository,
    post_mortem_repository,
    thesis_repository,
    user_repository,
)
from backend.services.chart_service import build_chart_data
from backend.services.check_service import CheckError, check_thesis
from backend.services.enhancement_service import EnhancementError, enhance_reasoning
from backend.services.extraction_service import ExtractionError, extract_and_save_thesis
from backend.services.verification_service import verify_document_against_thesis

router = APIRouter(prefix="/theses", tags=["theses"])


def get_llm_provider() -> GeminiProvider:
    return GeminiProvider()


@router.post("", response_model=ThesisOut)
def create_thesis(
    body: ThesisCreateRequest,
    db: Session = Depends(get_db),
    provider: GeminiProvider = Depends(get_llm_provider),
):
    user = user_repository.get_demo_user(db)
    try:
        thesis = extract_and_save_thesis(
            db, user_id=user.id, ticker=body.ticker, reasoning=body.reasoning, provider=provider
        )
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return thesis


@router.post("/enhance-reasoning", response_model=EnhanceReasoningOut)
def enhance_thesis_reasoning(
    body: EnhanceReasoningRequest,
    provider: GeminiProvider = Depends(get_llm_provider),
):
    """Sharpen the user's own wording. Returns a CANDIDATE — nothing is stored.

    Declared before the `/{thesis_id}` routes only for readability; FastAPI ranks
    static segments above dynamic ones regardless of order.

    Creating a thesis never calls this. It is an optional aid, and the response is
    shown beside the original for the user to accept or reject.
    """
    try:
        return enhance_reasoning(body.ticker, body.reasoning, provider=provider)
    except EnhancementError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("", response_model=list[ThesisOut])
def list_theses(db: Session = Depends(get_db)):
    user = user_repository.get_demo_user(db)
    return thesis_repository.list_theses_for_user(db, user_id=user.id)


@router.get("/{thesis_id}", response_model=ThesisOut)
def get_thesis(thesis_id: str, db: Session = Depends(get_db)):
    thesis = thesis_repository.get_thesis(db, thesis_id)
    if thesis is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    return thesis


@router.post("/{thesis_id}/documents", response_model=list[EvidenceEventOut])
def submit_document(thesis_id: str, body: DocumentSubmitRequest, db: Session = Depends(get_db)):
    if thesis_repository.get_thesis(db, thesis_id) is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    return verify_document_against_thesis(db, thesis_id, body.raw_text, body.title)


@router.get("/{thesis_id}/evidence", response_model=list[EvidenceEventOut])
def list_evidence(thesis_id: str, db: Session = Depends(get_db)):
    if thesis_repository.get_thesis(db, thesis_id) is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    return evidence_repository.list_evidence_for_thesis(db, thesis_id)


@router.get("/{thesis_id}/post-mortems", response_model=list[PostMortemOut])
def list_thesis_post_mortems(thesis_id: str, db: Session = Depends(get_db)):
    if thesis_repository.get_thesis(db, thesis_id) is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    return post_mortem_repository.list_post_mortems(db, thesis_id=thesis_id)


@router.post("/{thesis_id}/post-mortems", response_model=PostMortemOut)
def create_thesis_post_mortem(thesis_id: str, db: Session = Depends(get_db)):
    """Open a post-mortem on demand, without waiting for the thesis to break.

    Reflection is useful when a thesis merely wobbles, or when the user simply wants
    to think one through — so this deliberately does NOT require a "breaking" status.
    Unlike the automatic trigger there is no duplicate guard: asking for one is an
    explicit act, and refusing it would be surprising.
    """
    thesis = thesis_repository.get_thesis(db, thesis_id)
    if thesis is None:
        raise HTTPException(status_code=404, detail="Thesis not found")

    broken_core = next(
        (
            claim
            for claim in thesis.claims
            if claim.is_core and claim.status == BROKEN_CLAIM_STATUS
        ),
        None,
    )
    return post_mortem_repository.create_post_mortem(
        db,
        thesis_id=thesis_id,
        broken_claim_id=broken_core.id if broken_core is not None else None,
        status_at_break=thesis.status,
    )


@router.get("/{thesis_id}/chart", response_model=ChartDataOut)
def get_chart(
    thesis_id: str,
    days: int = Query(default=365, ge=1, le=1825),
    db: Session = Depends(get_db),
):
    """Prices for the thesis's ticker, annotated with its evidence and status changes.

    A price-source failure does NOT fail this request — it comes back with
    prices_unavailable set and the events intact, because a broken third party must
    never hide the user's own record.
    """
    chart = build_chart_data(db, thesis_id, days=days)
    if chart is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    return chart


@router.post("/{thesis_id}/check", response_model=CheckResultOut)
def run_check(thesis_id: str, limit: int = 3, db: Session = Depends(get_db)):
    if thesis_repository.get_thesis(db, thesis_id) is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    try:
        return check_thesis(db, thesis_id, limit=limit)
    except CheckError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except EdgarError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
