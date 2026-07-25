import os
import re

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from backend.adapters.gemini_provider import GeminiProvider
from backend.adapters.paste_source import PasteSource
from backend.adapters.rag_retriever import RagRetriever
from backend.domain.status import (
    compute_claim_status,
    compute_thesis_status,
    is_meaningful_change,
)
from backend.models.evidence_event import EvidenceEvent
from backend.ports.evidence_retriever import EvidenceRetriever
from backend.ports.llm_provider import LLMProvider
from backend.repositories import (
    alert_repository,
    document_repository,
    evidence_repository,
    thesis_repository,
)

load_dotenv()

# Verdicts that assert something about the claim and therefore require a grounded quote.
_ASSERTIVE_VERDICTS = {"supports", "contradicts"}

# How many passages to retrieve per claim.
#
# The trade-off is silent misses vs. tokens: too low and the decisive passage never
# reaches the model, which then answers "neutral" and looks confident about it — the
# failure mode with no visible symptom. Too high and every claim costs more tokens.
#
# Why 20: measured against a real NVDA 10-K (~880 chunks after cleaning), the decisive
# gross-margin passage ranked #14. 20 leaves headroom above that rather than fitting a
# single observation exactly — one filing is not a distribution.
#
# This is a STOPGAP. Raising k widens the net but does not improve ranking; the
# structural fix is hybrid keyword+vector retrieval, so an exact term like
# "gross margin" can't be out-ranked by generic financial prose.
#
# Deliberately not wrapped in try/except: a malformed RETRIEVAL_K should fail loudly at
# startup, not silently fall back to the default and leave someone believing they
# configured a value they didn't get.
_RETRIEVAL_K = int(os.getenv("RETRIEVAL_K") or 20)

# Separates retrieved passages in the prompt. They are non-contiguous excerpts, so the
# marker keeps the model from reading across a seam as if it were continuous prose (and
# a "quote" spanning two passages will fail the citation check, which is correct).
_PASSAGE_SEPARATOR = "\n\n---\n\n"

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
#
# ⚠️ `source_text` MUST be the RETRIEVED PASSAGES, never the full document. The model
# can only quote what it was actually shown, so checking against the whole document
# would let text the model never saw validate its quote — a hallucinated quote that
# happens to appear elsewhere in the filing would pass. Grounding is only meaningful
# against exactly the text that went into the prompt.
def quote_is_grounded(quote: str, source_text: str) -> bool:
    normalized_quote = _normalize(quote)
    if not normalized_quote:
        return False
    return normalized_quote in _normalize(source_text)


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


def _retrieval_query(claim) -> str:
    """What we search the document for.

    The statement alone is not enough: evidence is often phrased in the language of
    the conditions rather than the claim ("margins fell below 65%" never says
    "competitors caught up"). Combining all three gives retrieval the full semantic
    picture of what would prove or break this claim.
    """
    return f"{claim.statement} {claim.proof_condition} {claim.break_condition}"


def verify_document_against_thesis(
    db: Session,
    thesis_id: str,
    raw_text: str,
    title: str | None = None,
    source_type: str = "paste",
    retriever: EvidenceRetriever | None = None,
    provider: LLMProvider | None = None,
) -> list[EvidenceEvent]:
    # 1. DEDUP — hash the text (hashing is content-based, so PasteSource works for any
    # source) and skip re-verification if we've seen this exact content before.
    document_data = PasteSource().load(raw_text, title=title)
    existing = document_repository.get_document_by_hash(db, document_data.content_hash)
    if existing is not None:
        return evidence_repository.list_evidence_for_thesis(db, thesis_id)

    document = document_repository.create_document(
        db,
        source_type=source_type,
        title=document_data.title,
        content_hash=document_data.content_hash,
        raw_text=document_data.raw_text,
    )

    # 2. LOOP OVER CLAIMS
    thesis = thesis_repository.get_thesis(db, thesis_id)
    # Constructed here, not as default arguments, so the defaults aren't built at import
    # time and tests can inject fakes (NaiveRetriever, a stub provider).
    if retriever is None:
        retriever = RagRetriever()
    if provider is None:
        provider = GeminiProvider()
    created: list[EvidenceEvent] = []

    for claim in thesis.claims:
        # RETRIEVE FIRST — the model sees only the passages relevant to this claim,
        # not the whole filing.
        passages = retriever.retrieve(
            _retrieval_query(claim), raw_text, document.id, k=_RETRIEVAL_K
        )
        if not passages:
            # Nothing relevant (or an empty document): skip rather than prompt the AI
            # with no context, which would only invite a hallucinated verdict.
            continue

        retrieved_text = _PASSAGE_SEPARATOR.join(passages)

        verdict = provider.verify_claim(
            claim.statement, claim.proof_condition, claim.break_condition, retrieved_text
        )

        # 4. DECIDE PER VERDICT
        if verdict.verdict not in _ASSERTIVE_VERDICTS:
            continue  # "neutral" (or anything unexpected) — nothing to record

        # 3. CITATION CHECK — an assertive verdict must cite a quote that truly exists.
        # Checked against `retrieved_text`, i.e. exactly what the model was shown; see
        # the note above quote_is_grounded for why the full document would be wrong.
        if not quote_is_grounded(verdict.evidence_quote, retrieved_text):
            print(
                f"Rejected fabricated quote for claim {claim.id}: "
                f"{verdict.evidence_quote!r} not found in the passages retrieved from "
                f"document {document.id}"
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
