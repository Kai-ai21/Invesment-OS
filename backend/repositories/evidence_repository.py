from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.claim import Claim
from backend.models.evidence_event import EvidenceEvent


@dataclass(frozen=True)
class EvidenceSummary:
    """How much evidence a thesis has, and when the last of it arrived."""

    count: int
    last_at: datetime | None


EMPTY_SUMMARY = EvidenceSummary(count=0, last_at=None)


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


def events_by_claim(db: Session, thesis_ids: list[str]) -> dict[str, list[EvidenceEvent]]:
    """Every claim's evidence, for whole theses at a time, keyed by claim id.

    ⚠️ ONE QUERY FOR THE LOT, same reasoning as summarise_for_theses. The caller
    needs the actual verdicts and confidences (not just counts) because the score
    is recomputed from them by the domain — so this returns rows rather than an
    aggregate, but still in a single round trip rather than one per claim.

    Claims with no evidence are absent; a caller reading with `.get(id, [])` gets
    the empty list that means "pending", which is exactly right.
    """
    if not thesis_ids:
        return {}

    rows = (
        db.query(EvidenceEvent)
        .join(Claim, EvidenceEvent.claim_id == Claim.id)
        .filter(Claim.thesis_id.in_(thesis_ids))
        .all()
    )

    grouped: dict[str, list[EvidenceEvent]] = {}
    for event in rows:
        grouped.setdefault(event.claim_id, []).append(event)
    return grouped


def summarise_for_theses(db: Session, thesis_ids: list[str]) -> dict[str, EvidenceSummary]:
    """Evidence count and latest timestamp per thesis, for a whole list at once.

    ⚠️ ONE GROUPED QUERY, NOT ONE PER THESIS. The thesis list renders this on every
    card, so the obvious per-card `list_evidence_for_thesis` would put the list
    endpoint's cost in step with the number of theses — the classic N+1 — to
    display two integers. Aggregating in the database keeps it flat.

    Theses with no evidence are simply absent from the result; callers fall back to
    EMPTY_SUMMARY rather than this returning zero rows it had to invent.
    """
    if not thesis_ids:
        return {}

    rows = (
        db.query(
            Claim.thesis_id,
            func.count(EvidenceEvent.id),
            func.max(EvidenceEvent.created_at),
        )
        .join(EvidenceEvent, EvidenceEvent.claim_id == Claim.id)
        .filter(Claim.thesis_id.in_(thesis_ids))
        .group_by(Claim.thesis_id)
        .all()
    )
    return {
        thesis_id: EvidenceSummary(count=count, last_at=last_at)
        for thesis_id, count, last_at in rows
    }
