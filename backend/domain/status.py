from typing import Protocol


class ScoredEvent(Protocol):
    """Anything with a verdict and a confidence — an EvidenceEvent satisfies this."""

    verdict: str
    confidence: float


# The score bands are an ORDERED table, checked top to bottom, first match wins. Adding a
# new band means inserting one row here — no branching logic to touch. Each row is
# (min_score, inclusive, status); `inclusive` says whether the bound itself counts, because
# the bands genuinely differ on that: exactly 2.0 IS strongly_supported, but exactly 0.0 is
# NOT supported (equal support and contradiction is a weakening claim, not a healthy one).
CLAIM_STATUS_THRESHOLDS: list[tuple[float, bool, str]] = [
    (2.0, True, "strongly_supported"),
    (0.0, False, "supported"),
    (-1.0, False, "weakening"),
]

# Returned when a claim's score clears none of the bands above.
BROKEN_CLAIM_STATUS = "broken"

PENDING = "pending"

# The span a claim's score is READ AGAINST: the bottom of the lowest band it can
# sit in before breaking, up to the point where it is strongly supported. Derived
# from the table above rather than written out, so adding or moving a band cannot
# leave the scale the UI draws describing the old one.
#
# Exported because the UI draws a bar between these two points. Every number in
# that bar — the score and both ends of the range it is placed on — therefore
# comes from this module, and there is no threshold hard-coded in a component
# that a change here would silently invalidate.
CLAIM_SCORE_SCALE: tuple[float, float] = (
    CLAIM_STATUS_THRESHOLDS[-1][0],
    CLAIM_STATUS_THRESHOLDS[0][0],
)


def compute_claim_score(events: list[ScoredEvent]) -> float:
    """Support minus contradiction, each weighted by the confidence behind it.

    Split out of compute_claim_status so the number itself can be shown to the
    user — the UI renders it beside the claim, which is what makes a status
    legible ("+1.67" explains why a claim with one contradiction is still
    supported). It is deliberately EXPORTED RATHER THAN REIMPLEMENTED anywhere
    else: two copies of this loop would eventually disagree, and the one on
    screen would be the one nobody could trace.
    """
    score = 0.0
    for event in events:
        if event.verdict == "supports":
            score += event.confidence
        elif event.verdict == "contradicts":
            score -= event.confidence
        # any other verdict (e.g. "neutral") contributes nothing
    return score


def compute_claim_status(events: list[ScoredEvent]) -> str:
    """Score a claim's evidence and map that score onto a status band."""
    if not events:
        return PENDING

    score = compute_claim_score(events)

    for min_score, inclusive, status in CLAIM_STATUS_THRESHOLDS:
        if score >= min_score if inclusive else score > min_score:
            return status

    return BROKEN_CLAIM_STATUS


def compute_thesis_status(claims: list[tuple[str, bool]]) -> str:
    """Roll individual claim statuses up into one thesis status. Rules are ordered."""
    if not claims or all(status == PENDING for status, _ in claims):
        return PENDING

    if any(is_core and status == BROKEN_CLAIM_STATUS for status, is_core in claims):
        return "breaking"

    if any(status in {BROKEN_CLAIM_STATUS, "weakening"} for status, _ in claims):
        return "weakening"

    return "strengthening"


def is_meaningful_change(prev_status: str, new_status: str) -> bool:
    """Whether a status transition is worth acting on. Named so the rule has one home."""
    return prev_status != new_status
