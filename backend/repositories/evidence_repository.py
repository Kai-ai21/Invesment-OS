from sqlalchemy.orm import Session

from backend.models.claim import Claim
from backend.models.evidence_event import EvidenceEvent


def create_evidence_event(
    db: Session,
    *,
    claim_id: str,
    document_id: str,
    verdict: str,
    confidence: float,
    evidence_quote: str,
    reasoning: str,
) -> EvidenceEvent:
    event = EvidenceEvent(
        claim_id=claim_id,
        document_id=document_id,
        verdict=verdict,
        confidence=confidence,
        evidence_quote=evidence_quote,
        reasoning=reasoning,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_evidence_for_claim(db: Session, claim_id: str) -> list[EvidenceEvent]:
    return (
        db.query(EvidenceEvent)
        .filter(EvidenceEvent.claim_id == claim_id)
        .order_by(EvidenceEvent.created_at.desc())
        .all()
    )


def list_evidence_for_thesis(db: Session, thesis_id: str) -> list[EvidenceEvent]:
    # Join through claims so we return evidence for every claim belonging to the thesis.
    return (
        db.query(EvidenceEvent)
        .join(Claim, EvidenceEvent.claim_id == Claim.id)
        .filter(Claim.thesis_id == thesis_id)
        .order_by(EvidenceEvent.created_at.desc())
        .all()
    )
