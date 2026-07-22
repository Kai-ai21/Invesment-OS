from sqlalchemy.orm import Session

from backend.domain.claim import ClaimData
from backend.models.claim import Claim
from backend.models.thesis import Thesis


def create_thesis(db: Session, *, user_id: str, ticker: str, reasoning_raw: str) -> Thesis:
    thesis = Thesis(user_id=user_id, ticker=ticker, reasoning_raw=reasoning_raw)
    db.add(thesis)
    db.commit()
    db.refresh(thesis)
    return thesis


def add_claims(db: Session, *, thesis_id: str, claims: list[ClaimData]) -> list[Claim]:
    db_claims = [
        Claim(
            thesis_id=thesis_id,
            statement=claim.statement,
            proof_condition=claim.proof_condition,
            break_condition=claim.break_condition,
            is_core=claim.is_core,
        )
        for claim in claims
    ]
    db.add_all(db_claims)
    db.commit()
    return db_claims


def set_status(db: Session, *, thesis_id: str, status: str) -> None:
    thesis = db.get(Thesis, thesis_id)
    thesis.status = status
    db.commit()


def get_thesis(db: Session, thesis_id: str) -> Thesis | None:
    return db.get(Thesis, thesis_id)


def list_theses_for_user(db: Session, user_id: str) -> list[Thesis]:
    return db.query(Thesis).filter(Thesis.user_id == user_id).order_by(Thesis.created_at.desc()).all()
