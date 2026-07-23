import re

from sqlalchemy.orm import Session

from backend.adapters.gemini_provider import GeminiProvider
from backend.adapters.paste_source import PasteSource
from backend.domain.status import (
    compute_claim_status,
    compute_thesis_status,
    is_meaningful_change,
)
from backend.models.evidence_event import EvidenceEvent
from backend.repositories import (
    alert_repository,
    document_repository,
    evidence_repository,
    thesis_repository,
)

# Verdicts that assert something about the claim and therefore require a grounded quote.
_ASSERTIVE_VERDICTS = {"supports", "contradicts"}

_CURLY_TO_STRAIGHT = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})


def _normalize(text: str) -> str:
    text = text.translate(_CURLY_TO_STRAIGHT)  # curly quotes -> straight quotes
    text = text.lower()
    text = re.sub(r"\s+", " ", text)  # collapse any run of whitespace to a single space
    return text.strip()


# We normalize before comparing so the citation check is FORGIVING about formatting
# (casing, whitespace, curly vs. straight quotes — all cosmetic differences the model
# might introduce) but STRICT about content: the quoted words must genuinely appear in
# the source. This is what stops the model from citing a fabricated quote.
def quote_is_grounded(quote: str, document_text: str) -> bool:
    normalized_quote = _normalize(quote)
    if not normalized_quote:
        return False
    return normalized_quote in _normalize(document_text)


def recompute_thesis(db: Session, thesis_id: str) -> tuple[str, str]:
    """Re-score every claim from its evidence, roll it up to the thesis, and alert on change."""
    thesis = thesis_repository.get_thesis(db, thesis_id)
    prev_status = thesis.status

    # The status functions are pure: hand them plain data, never the session.
    claim_states: list[tuple[str, bool]] = []
    for claim in thesis.claims:
        events = evidence_repository.list_evidence_for_claim(db, claim.id)
        claim.status = compute_claim_status(events)
        claim_states.append((claim.status, claim.is_core))

    new_status = compute_thesis_status(claim_states)
    thesis.status = new_status

    if is_meaningful_change(prev_status, new_status):
        alert_repository.create_alert(
            db,
            thesis_id=thesis_id,
            prev_status=prev_status,
            new_status=new_status,
            summary=f"{thesis.ticker} thesis moved from {prev_status} to {new_status}",
        )

    db.commit()
    return prev_status, new_status


def verify_document_against_thesis(
    db: Session, thesis_id: str, raw_text: str, title: str | None = None
) -> list[EvidenceEvent]:
    # 1. DEDUP — load + hash the text, and skip re-verification if we've seen it before.
    document_data = PasteSource().load(raw_text, title=title)
    existing = document_repository.get_document_by_hash(db, document_data.content_hash)
    if existing is not None:
        return evidence_repository.list_evidence_for_thesis(db, thesis_id)

    document = document_repository.create_document(
        db,
        source_type=document_data.source_type,
        title=document_data.title,
        content_hash=document_data.content_hash,
        raw_text=document_data.raw_text,
    )

    # 2. LOOP OVER CLAIMS
    thesis = thesis_repository.get_thesis(db, thesis_id)
    provider = GeminiProvider()
    created: list[EvidenceEvent] = []

    for claim in thesis.claims:
        verdict = provider.verify_claim(
            claim.statement, claim.proof_condition, claim.break_condition, raw_text
        )

        # 4. DECIDE PER VERDICT
        if verdict.verdict not in _ASSERTIVE_VERDICTS:
            continue  # "neutral" (or anything unexpected) — nothing to record

        # 3. CITATION CHECK — an assertive verdict must cite a quote that truly exists.
        if not quote_is_grounded(verdict.evidence_quote, raw_text):
            print(
                f"Rejected fabricated quote for claim {claim.id}: "
                f"{verdict.evidence_quote!r} not found in document {document.id}"
            )
            continue

        event = evidence_repository.create_evidence_event(
            db,
            claim_id=claim.id,
            document_id=document.id,
            verdict=verdict.verdict,
            confidence=verdict.confidence,
            evidence_quote=verdict.evidence_quote,
            reasoning=verdict.reasoning,
        )
        created.append(event)

    # 5. Re-score claims and the thesis now that new evidence has landed.
    recompute_thesis(db, thesis_id)

    # 6. Return only the events we actually created.
    return created
