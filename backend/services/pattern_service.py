"""Finds recurring behaviours across the user's answered reflections.

This is the most sensitive AI output in the product: everywhere else the model makes
claims about a DOCUMENT, here it makes claims about a PERSON. So the evidence bar is
higher, not lower — a pattern that cannot name at least two real reflections it came
from is discarded rather than shown.
"""

from sqlalchemy.orm import Session

from backend.adapters.gemini_provider import GeminiProvider
from backend.models.pattern import Pattern
from backend.ports.llm_provider import LLMProvider
from backend.repositories import pattern_repository, post_mortem_repository

# Below this many ANSWERED reflections, the feature stays silent.
#
# Not a UI nicety — a real constraint on what can be known. An AI asked to find patterns
# in two data points will always find some, because any two stories share a surface
# feature. The output would be indistinguishable from insight while being noise, and
# it would be noise about the user's own judgement, which is exactly the thing they are
# least able to check.
MINIMUM_POST_MORTEMS = 3

# One reflection is an anecdote. This is the same rule the prompt states, enforced here
# because a prompt is a request and this is a guarantee.
MINIMUM_CITATIONS_PER_PATTERN = 2


def _to_payload(post_mortem) -> dict:
    return {
        "post_mortem_id": post_mortem.id,
        "ticker": post_mortem.ticker,
        "broken_claim_statement": post_mortem.broken_claim_statement or "(not recorded)",
        "prompt_question": post_mortem.prompt_question or "(not recorded)",
        "user_response": post_mortem.user_response,
        "created_at": post_mortem.created_at.isoformat(),
    }


def pattern_is_grounded(
    source_post_mortem_ids: list[str], supplied_ids: set[str]
) -> bool:
    """Every cited id must be one we actually supplied, and there must be at least two.

    The same discipline as verification's quote_is_grounded, applied to citations
    instead of quotations: a model that cites an id it was never given has invented its
    evidence, and an "observation" about someone's behaviour built on invented evidence
    is the worst thing this product could show them.
    """
    unique_ids = set(source_post_mortem_ids)
    if len(unique_ids) < MINIMUM_CITATIONS_PER_PATTERN:
        return False
    return unique_ids.issubset(supplied_ids)


def generate_patterns(
    db: Session, user_id: str, provider: LLMProvider | None = None
) -> list[Pattern]:
    """Rebuild the pattern set from every answered post-mortem.

    Returns [] without calling the AI when there is not enough material. Regenerating
    REPLACES the previous set rather than adding to it.
    """
    answered = [
        item
        for item in post_mortem_repository.list_post_mortems(db, user_id)
        if item.user_response is not None
    ]

    # Checked before the provider is constructed, so the "not enough data" path costs
    # nothing and needs no API key.
    if len(answered) < MINIMUM_POST_MORTEMS:
        return []

    if provider is None:
        provider = GeminiProvider()

    supplied_ids = {item.id for item in answered}
    candidates = provider.generate_patterns([_to_payload(item) for item in answered])

    # An empty list is a valid, expected answer — most small sets share nothing real.
    # Still replace the old set, so a pattern that no longer holds disappears rather
    # than lingering because this run found nothing.
    pattern_repository.delete_all_patterns(db, user_id)

    saved: list[Pattern] = []
    for candidate in candidates:
        if not pattern_is_grounded(candidate.source_post_mortem_ids, supplied_ids):
            print(
                f"Rejected ungrounded pattern {candidate.statement!r}: "
                f"cites {candidate.source_post_mortem_ids}"
            )
            continue
        saved.append(
            pattern_repository.create_pattern(
                db,
                user_id=user_id,
                statement=candidate.statement,
                # Deduplicated and ordered so the stored citations match what was
                # actually validated.
                evidence_post_mortem_ids=sorted(set(candidate.source_post_mortem_ids)),
            )
        )
    return saved
