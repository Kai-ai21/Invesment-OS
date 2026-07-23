from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.adapters.edgar_source import EdgarError
from backend.adapters.gemini_provider import GeminiProvider
from backend.api.schemas import (
    CheckResultOut,
    DocumentSubmitRequest,
    EvidenceEventOut,
    ThesisCreateRequest,
    ThesisOut,
)
from backend.models.database import get_db
from backend.repositories import evidence_repository, thesis_repository, user_repository
from backend.services.check_service import CheckError, check_thesis
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
