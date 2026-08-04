from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.adapters.edgar_source import EdgarError
from backend.adapters.gemini_provider import GeminiProvider
from backend.api.schemas import (
    ChartDataOut,
    ClaimOut,
    EnhanceReasoningOut,
    EnhanceReasoningRequest,
    CheckResultOut,
    DocumentSubmitRequest,
    EvidenceEventOut,
    PostMortemOut,
    ThesisCreateRequest,
    ThesisOut,
)
from backend.api.deps import get_current_user
from backend.domain.status import BROKEN_CLAIM_STATUS, compute_claim_score
from backend.models.database import get_db
from backend.models.user import User
from backend.repositories import (
    evidence_repository,
    post_mortem_repository,
    thesis_repository,
)
from backend.repositories.evidence_repository import EMPTY_SUMMARY, EvidenceSummary
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
    user: User = Depends(get_current_user),
):
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
    user: User = Depends(get_current_user),
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


def _thesis_out(
    thesis,
    summaries: dict[str, EvidenceSummary],
    events_by_claim: dict[str, list],
) -> ThesisOut:
    """A thesis with its evidence rollup, and each claim with its score.

    Composed here rather than stored on the rows: every one of these is derived
    from the append-only events table, so recomputing means they can never
    disagree with the events themselves — and there is no counter or cached score
    to forget to update when a check writes new evidence.

    ⚠️ THE SCORE COMES FROM THE DOMAIN, not from a second loop here. This calls
    the same compute_claim_score that compute_claim_status calls, so the number
    shown to the user is by construction the number the status was decided on.
    """
    summary = summaries.get(thesis.id, EMPTY_SUMMARY)

    claims = []
    for claim in thesis.claims:
        events = events_by_claim.get(claim.id, [])
        claims.append(
            ClaimOut.model_validate(claim).model_copy(
                update={
                    "evidence_count": len(events),
                    # None, not 0.0, with nothing to score — see ClaimOut.
                    "score": compute_claim_score(events) if events else None,
                }
            )
        )

    return ThesisOut.model_validate(thesis).model_copy(
        update={
            "claims": claims,
            "evidence_count": summary.count,
            "last_evidence_at": summary.last_at,
        }
    )


@router.get("", response_model=list[ThesisOut])
def list_theses(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    theses = thesis_repository.list_theses_for_user(db, user_id=user.id)
    ids = [thesis.id for thesis in theses]
    # Two queries for the whole list, however many theses it holds.
    summaries = evidence_repository.summarise_for_theses(db, ids, user.id)
    events = evidence_repository.events_by_claim(db, ids, user.id)
    return [_thesis_out(thesis, summaries, events) for thesis in theses]


@router.get("/{thesis_id}", response_model=ThesisOut)
def get_thesis(
    thesis_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """⚠️ 404, NOT 403, for a thesis that exists and is someone else's.

    The repository returns None for both cases, so there is nothing here that could
    leak the difference. A 403 would tell whoever is walking uuids that they had just
    found a real one.
    """
    thesis = thesis_repository.get_thesis(db, thesis_id, user.id)
    if thesis is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    return _thesis_out(
        thesis,
        evidence_repository.summarise_for_theses(db, [thesis.id], user.id),
        evidence_repository.events_by_claim(db, [thesis.id], user.id),
    )


@router.post("/{thesis_id}/documents", response_model=list[EvidenceEventOut])
def submit_document(
    thesis_id: str,
    body: DocumentSubmitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if thesis_repository.get_thesis(db, thesis_id, user.id) is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    return verify_document_against_thesis(db, thesis_id, user.id, body.raw_text, body.title)


@router.get("/{thesis_id}/evidence", response_model=list[EvidenceEventOut])
def list_evidence(
    thesis_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if thesis_repository.get_thesis(db, thesis_id, user.id) is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    return evidence_repository.list_evidence_for_thesis(db, thesis_id, user.id)


@router.get("/{thesis_id}/post-mortems", response_model=list[PostMortemOut])
def list_thesis_post_mortems(
    thesis_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if thesis_repository.get_thesis(db, thesis_id, user.id) is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    return post_mortem_repository.list_post_mortems(db, user.id, thesis_id=thesis_id)


@router.post("/{thesis_id}/post-mortems", response_model=PostMortemOut)
def create_thesis_post_mortem(
    thesis_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Open a post-mortem on demand, without waiting for the thesis to break.

    Reflection is useful when a thesis merely wobbles, or when the user simply wants
    to think one through — so this deliberately does NOT require a "breaking" status.
    Unlike the automatic trigger there is no duplicate guard: asking for one is an
    explicit act, and refusing it would be surprising.
    """
    thesis = thesis_repository.get_thesis(db, thesis_id, user.id)
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
        user_id=user.id,
        broken_claim_id=broken_core.id if broken_core is not None else None,
        status_at_break=thesis.status,
    )


@router.get("/{thesis_id}/chart", response_model=ChartDataOut)
def get_chart(
    thesis_id: str,
    days: int = Query(default=365, ge=1, le=1825),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Prices for the thesis's ticker, annotated with its evidence and status changes.

    A price-source failure does NOT fail this request — it comes back with
    prices_unavailable set and the events intact, because a broken third party must
    never hide the user's own record.
    """
    chart = build_chart_data(db, thesis_id, user.id, days=days)
    if chart is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    return chart


@router.post("/{thesis_id}/check", response_model=CheckResultOut)
def run_check(
    thesis_id: str,
    limit: int = 3,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """⚠️ SCOPED BEFORE ANY WORK IS DONE. Unscoped, this let anyone spend AI calls
    and SEC requests against a stranger's thesis, and write evidence that moves its
    status — the most expensive IDOR in the app, in both senses."""
    if thesis_repository.get_thesis(db, thesis_id, user.id) is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    try:
        return check_thesis(db, thesis_id, user.id, limit=limit)
    except CheckError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except EdgarError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
