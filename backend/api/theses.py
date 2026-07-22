from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from adapters.gemini_provider import GeminiProvider
from api.schemas import ThesisCreateRequest, ThesisOut
from models.database import get_db
from repositories import thesis_repository, user_repository
from services.extraction_service import ExtractionError, extract_and_save_thesis

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
