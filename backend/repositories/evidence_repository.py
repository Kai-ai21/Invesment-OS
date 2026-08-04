from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.claim import Claim
from backend.models.evidence_event import EvidenceEvent
from backend.models.thesis import Thesis


@dataclass(frozen=True)
class EvidenceSummary:
    """How much evidence a thesis has, and when the last of it arrived."""

    count: int
    last_at: datetime | None


EMPTY_SUMMARY = EvidenceSummary(count=0, last_at=None)


def _owned(query, user_id: str):
    """Constrain an EvidenceEvent query to one user, through claim → thesis.

    ⚠️ EVERY READ IN THIS MODULE GOES THROUGH HERE. Evidence is two joins from a
    user — event → claim → thesis → user_id — and writing that chain out at each call
    site is how one of them ends up with only the first join. There is exactly one
    copy, and every function below composes it.
    """
    return (
        query.join(Claim, EvidenceEvent.claim_id == Claim.id)
        .join(Thesis, Claim.thesis_id == Thesis.id)
        .filter(Thesis.user_id == user_id)
    )


def claim_is_owned(db: Session, claim_id: str, user_id: str) -> bool:
    """Whether this claim hangs off a thesis the user owns."""
    return (
        db.query(Claim.id)
        .join(Thesis, Claim.thesis_id == Thesis.id)
        .filter(Claim.id == claim_id, Thesis.user_id == user_id)
        .first()
        is not None
    )


def create_evidence_event(
    db: Session,
    *,
    claim_id: str,
    user_id: str,
    document_id: str,
    verdict: str,
    confidence: float,
    evidence_quote: str,
    reasoning: str,
) -> EvidenceEvent | None:
    """Record a verdict against a claim. None when the claim is not this user's.

    ⚠️ A SCOPED WRITE, not just a scoped read. Evidence is what the status engine
    computes from, so an unscoped create lets one user move another user's thesis
    from "active" to "breaking" — a data-integrity hole, not only a disclosure one.
    """
    if not claim_is_owned(db, claim_id, user_id):
        return None

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


def thesis_has_evidence_from_document(
    db: Session, *, thesis_id: str, document_id: str, user_id: str
) -> bool:
    """Whether this thesis has already been verified against this document.

    The dedup question verification actually needs. `documents` is shared across all
    users by content hash, so "does this document exist" answers a different question
    entirely — see the note at the dedup step in verification_service.
    """
    return (
        _owned(db.query(EvidenceEvent), user_id)
        .filter(
            Claim.thesis_id == thesis_id,
            EvidenceEvent.document_id == document_id,
        )
        .first()
        is not None
    )


def list_evidence_for_claim(
    db: Session, claim_id: str, user_id: str
) -> list[EvidenceEvent]:
    return (
        _owned(db.query(EvidenceEvent), user_id)
        .filter(EvidenceEvent.claim_id == claim_id)
        .order_by(EvidenceEvent.created_at.desc())
        .all()
    )


def list_evidence_for_thesis(
    db: Session, thesis_id: str, user_id: str
) -> list[EvidenceEvent]:
    # Join through claims so we return evidence for every claim belonging to the
    # thesis, and on through theses so we return nothing at all for someone else's.
    return (
        _owned(db.query(EvidenceEvent), user_id)
        .filter(Claim.thesis_id == thesis_id)
        .order_by(EvidenceEvent.created_at.desc())
        .all()
    )


def events_by_claim(
    db: Session, thesis_ids: list[str], user_id: str
) -> dict[str, list[EvidenceEvent]]:
    """Every claim's evidence, for whole theses at a time, keyed by claim id.

    ⚠️ ONE QUERY FOR THE LOT, same reasoning as summarise_for_theses. The caller
    needs the actual verdicts and confidences (not just counts) because the score
    is recomputed from them by the domain — so this returns rows rather than an
    aggregate, but still in a single round trip rather than one per claim.

    Claims with no evidence are absent; a caller reading with `.get(id, [])` gets
    the empty list that means "pending", which is exactly right.

    ⚠️ THE ids ARE NOT TRUSTED. They arrive from the caller, so an unscoped version
    would happily aggregate over any thesis id that was passed in. The join filters
    them regardless.
    """
    if not thesis_ids:
        return {}

    rows = (
        _owned(db.query(EvidenceEvent), user_id)
        .filter(Claim.thesis_id.in_(thesis_ids))
        .all()
    )

    grouped: dict[str, list[EvidenceEvent]] = {}
    for event in rows:
        grouped.setdefault(event.claim_id, []).append(event)
    return grouped


def summarise_for_theses(
    db: Session, thesis_ids: list[str], user_id: str
) -> dict[str, EvidenceSummary]:
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
        .join(Thesis, Claim.thesis_id == Thesis.id)
        .filter(Claim.thesis_id.in_(thesis_ids), Thesis.user_id == user_id)
        .group_by(Claim.thesis_id)
        .all()
    )
    return {
        thesis_id: EvidenceSummary(count=count, last_at=last_at)
        for thesis_id, count, last_at in rows
    }
