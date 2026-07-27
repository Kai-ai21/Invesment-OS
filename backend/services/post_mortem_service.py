"""Generates the reflection question attached to a post-mortem.

Called LAZILY — when the frontend goes to display a post-mortem — never during
verification. A check already spends one LLM call per claim; adding a reflection
question to that path would slow the thing the user is actually waiting for, to
produce text they may not read for days.
"""

import re

from sqlalchemy.orm import Session

from backend.adapters.gemini_provider import GeminiProvider
from backend.models.post_mortem import PostMortem
from backend.ports.llm_provider import LLMProvider
from backend.repositories import evidence_repository, post_mortem_repository
from backend.services.verification_service import _normalize

# Enough contradicting evidence to make the question specific, few enough to keep the
# prompt tight. The newest quotes are the ones that broke the claim.
MAX_EVIDENCE_QUOTES = 3

# Double quotes only — straight and curly. Single quotes are skipped deliberately:
# apostrophes in "don't" and possessives would produce garbage spans.
#
# The curly variants are written as \u escapes rather than literal characters on
# purpose: models emit “smart quotes” constantly, and if those two characters were ever
# lost in an encoding round-trip the regex would still compile, still match straight
# quotes, and silently stop detecting the most common case — a grounding check that
# passes everything while looking like it works.
_QUOTED_SPAN = re.compile("[\"“”]([^\"“”]+)[\"“”]")


class PostMortemError(Exception):
    """The question could not be generated."""


class PostMortemNotFound(PostMortemError):
    """No such post-mortem — distinct from one that exists but cannot be asked about,
    so the API can answer 404 rather than 422."""


def _quoted_spans(text: str) -> list[str]:
    """Every double-quoted span in the text — the model's claims about what the
    source said."""
    return [span.strip() for span in _QUOTED_SPAN.findall(text) if span.strip()]


def question_is_grounded(question: str, source_material: list[str]) -> bool:
    """Every quoted span in the question must appear in the material we supplied.

    Same normalise-and-contain approach as verification_service.quote_is_grounded:
    forgiving about casing, whitespace and curly-vs-straight quotes, strict about
    content. A question that quotes something never provided is inventing evidence,
    which is exactly what would make this feature untrustworthy.

    NOTE the source material is everything given to the model — the evidence quotes,
    the claim, AND the investor's own reasoning — not the evidence quotes alone. A
    question that quotes the investor back to themselves ("you wrote that margins would
    hold") is properly grounded; rejecting it would push good questions to the fallback
    for no reason. Hallucination is still caught, because invented text appears in none
    of it.

    A question with no quoted spans passes: it is paraphrasing, which the prompt allows
    outside of quotation marks.
    """
    haystack = _normalize(" ".join(source_material))
    return all(_normalize(span) in haystack for span in _quoted_spans(question))


def _fallback_question(claim_statement: str) -> str:
    """Used when the model twice returned something ungrounded.

    Deliberately dull and entirely safe: it quotes the claim statement verbatim and
    adds nothing else, so it cannot invent, judge, or advise. A plain question beats a
    vivid one that might be fabricated.
    """
    return (
        f'This claim no longer holds: "{claim_statement}" '
        "What made you confident in it when you wrote the thesis?"
    )


def generate_question(
    db: Session,
    post_mortem_id: str,
    provider: LLMProvider | None = None,
    force: bool = False,
) -> PostMortem:
    """Write and store the reflection question for a post-mortem.

    Idempotent by default: an existing question is returned untouched, so the frontend
    can call this every time it displays a post-mortem without burning a token or
    changing wording under the user. `force=True` regenerates deliberately.
    """
    post_mortem = post_mortem_repository.get_post_mortem(db, post_mortem_id)
    if post_mortem is None:
        raise PostMortemNotFound(f"Post-mortem {post_mortem_id} not found")

    if post_mortem.prompt_question and not force:
        return post_mortem

    claim = post_mortem.broken_claim
    if claim is None:
        # A manually-opened post-mortem on a thesis with no broken core claim has
        # nothing specific to ask about, and the prompt forbids generic questions.
        raise PostMortemError(
            f"Post-mortem {post_mortem_id} has no broken claim to reflect on"
        )

    if provider is None:
        provider = GeminiProvider()

    contradicting = [
        event.evidence_quote
        for event in evidence_repository.list_evidence_for_claim(db, claim.id)
        if event.verdict == "contradicts" and event.evidence_quote
    ][:MAX_EVIDENCE_QUOTES]

    # Everything the model is shown, and therefore everything it may quote.
    source_material = [
        post_mortem.thesis.reasoning_raw,
        claim.statement,
        claim.proof_condition,
        claim.break_condition,
        *contradicting,
    ]

    question = None
    # Two attempts: models sometimes embellish on the first pass and comply when the
    # same prompt is simply run again. A third try would just be paying for noise.
    for _ in range(2):
        candidate = provider.generate_reflection_question(
            original_reasoning=post_mortem.thesis.reasoning_raw,
            broken_claim_statement=claim.statement,
            broken_claim_proof=claim.proof_condition,
            broken_claim_break=claim.break_condition,
            evidence_quotes=contradicting,
        )
        if candidate and question_is_grounded(candidate, source_material):
            question = candidate
            break
        print(
            f"Rejected ungrounded reflection question for post-mortem "
            f"{post_mortem_id}: {candidate!r}"
        )

    post_mortem.prompt_question = question or _fallback_question(claim.statement)
    db.commit()
    db.refresh(post_mortem)
    return post_mortem
