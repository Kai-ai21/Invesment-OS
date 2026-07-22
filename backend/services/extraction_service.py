from sqlalchemy.orm import Session

from models.thesis import Thesis
from ports.llm_provider import LLMProvider
from repositories import thesis_repository

MAX_ATTEMPTS = 3  # 1 initial attempt + 2 retries


class ExtractionError(Exception):
    pass


def _validate(claims) -> None:
    if not (2 <= len(claims) <= 4):
        raise ExtractionError(f"Expected 2-4 claims, got {len(claims)}")
    for claim in claims:
        if not claim.statement.strip() or not claim.proof_condition.strip() or not claim.break_condition.strip():
            raise ExtractionError("Claim is missing a required field")


def extract_and_save_thesis(
    db: Session, *, user_id: str, ticker: str, reasoning: str, provider: LLMProvider
) -> Thesis:
    last_error: Exception | None = None

    for _ in range(MAX_ATTEMPTS):
        try:
            claims = provider.extract_claims(ticker, reasoning)
            _validate(claims)
        except Exception as exc:  # covers provider failures and validation failures alike
            last_error = exc
            continue

        thesis = thesis_repository.create_thesis(db, user_id=user_id, ticker=ticker, reasoning_raw=reasoning)
        thesis_repository.add_claims(db, thesis_id=thesis.id, claims=claims)
        thesis_repository.set_status(db, thesis_id=thesis.id, status="active")
        db.refresh(thesis)
        return thesis

    raise ExtractionError(f"Claim extraction failed after {MAX_ATTEMPTS} attempts: {last_error}")
