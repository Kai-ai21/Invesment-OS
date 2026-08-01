from dataclasses import dataclass

import pytest

from backend.domain.status import (
    CLAIM_SCORE_SCALE,
    CLAIM_STATUS_THRESHOLDS,
    compute_claim_score,
    compute_claim_status,
    compute_thesis_status,
    is_meaningful_change,
)


@dataclass
class FakeEvent:
    """Stand-in for an EvidenceEvent — the status engine only needs these two fields."""

    verdict: str
    confidence: float


# --- compute_claim_status ---------------------------------------------------------


def test_claim_with_no_events_is_pending():
    # Arrange
    events = []

    # Act
    status = compute_claim_status(events)

    # Assert
    assert status == "pending"


def test_single_high_confidence_support_is_supported():
    # Arrange
    events = [FakeEvent(verdict="supports", confidence=0.9)]

    # Act
    status = compute_claim_status(events)

    # Assert
    assert status == "supported"


def test_two_strong_supports_are_strongly_supported():
    # Arrange — 1.0 + 1.0 = 2.0, which clears the inclusive 2.0 bound
    events = [
        FakeEvent(verdict="supports", confidence=1.0),
        FakeEvent(verdict="supports", confidence=1.0),
    ]

    # Act
    status = compute_claim_status(events)

    # Assert
    assert status == "strongly_supported"


def test_two_strong_contradictions_are_broken():
    # Arrange — score of -1.8 falls below every band
    events = [
        FakeEvent(verdict="contradicts", confidence=0.9),
        FakeEvent(verdict="contradicts", confidence=0.9),
    ]

    # Act
    status = compute_claim_status(events)

    # Assert
    assert status == "broken"


def test_one_weak_contradiction_is_weakening():
    # Arrange — score of -0.5 is still above the -1.0 bound
    events = [FakeEvent(verdict="contradicts", confidence=0.5)]

    # Act
    status = compute_claim_status(events)

    # Assert
    assert status == "weakening"


def test_equal_support_and_contradiction_is_weakening():
    # Arrange — score is exactly 0.0, which must NOT count as supported
    events = [
        FakeEvent(verdict="supports", confidence=0.8),
        FakeEvent(verdict="contradicts", confidence=0.8),
    ]

    # Act
    status = compute_claim_status(events)

    # Assert
    assert status == "weakening"


def test_unknown_verdicts_are_ignored():
    # Arrange — identical evidence, but one list carries extra non-scoring verdicts
    supporting_only = [FakeEvent(verdict="supports", confidence=0.9)]
    with_unknown_verdicts = [
        FakeEvent(verdict="supports", confidence=0.9),
        FakeEvent(verdict="neutral", confidence=1.0),
        FakeEvent(verdict="banana", confidence=5.0),
    ]

    # Act
    status = compute_claim_status(with_unknown_verdicts)

    # Assert
    assert status == compute_claim_status(supporting_only)
    assert status == "supported"


# --- compute_thesis_status --------------------------------------------------------


def test_thesis_with_no_claims_is_pending():
    # Arrange
    claims = []

    # Act
    status = compute_thesis_status(claims)

    # Assert
    assert status == "pending"


def test_thesis_with_all_claims_pending_is_pending():
    # Arrange
    claims = [("pending", True), ("pending", False)]

    # Act
    status = compute_thesis_status(claims)

    # Assert
    assert status == "pending"


def test_thesis_with_broken_core_claim_is_breaking():
    # Arrange — the broken claim is a core one, which outranks the healthy claims
    claims = [("broken", True), ("supported", False)]

    # Act
    status = compute_thesis_status(claims)

    # Assert
    assert status == "breaking"


def test_thesis_with_broken_minor_claim_is_weakening():
    # Arrange — core claims are fine, only a minor claim is broken
    claims = [("strongly_supported", True), ("broken", False)]

    # Act
    status = compute_thesis_status(claims)

    # Assert
    assert status == "weakening"


def test_thesis_with_all_claims_supported_is_strengthening():
    # Arrange
    claims = [("supported", True), ("strongly_supported", False)]

    # Act
    status = compute_thesis_status(claims)

    # Assert
    assert status == "strengthening"


# --- is_meaningful_change ---------------------------------------------------------


def test_same_status_is_not_a_meaningful_change():
    # Arrange / Act
    changed = is_meaningful_change("supported", "supported")

    # Assert
    assert changed is False


def test_different_status_is_a_meaningful_change():
    # Arrange / Act
    changed = is_meaningful_change("supported", "weakening")

    # Assert
    assert changed is True


# --- compute_claim_score ----------------------------------------------------------
#
# The score is now SHOWN to the user beside the status, so it is part of the
# contract rather than an internal step. These pin the two properties that matter:
# it is the number the status was decided on, and it can leave the band range.


def test_score_is_support_minus_contradiction_weighted_by_confidence():
    # Arrange
    events = [
        FakeEvent("supports", 0.9),
        FakeEvent("supports", 0.8),
        FakeEvent("contradicts", 0.5),
    ]

    # Act
    score = compute_claim_score(events)

    # Assert
    assert score == pytest.approx(1.2)


def test_neutral_evidence_moves_the_score_neither_way():
    # Arrange
    scored = [FakeEvent("supports", 0.6)]
    with_neutral = [*scored, FakeEvent("neutral", 0.95)]

    # Act / Assert — a neutral read is still evidence, but it is not a vote.
    assert compute_claim_score(with_neutral) == compute_claim_score(scored)


def test_score_agrees_with_the_status_it_produced():
    # Arrange — the case the UI exists to explain: a contradiction on the record,
    # and a claim that is supported anyway because the support outweighed it.
    events = [
        FakeEvent("supports", 0.9),
        FakeEvent("supports", 0.85),
        FakeEvent("contradicts", 0.7),
    ]

    # Act
    score = compute_claim_score(events)
    status = compute_claim_status(events)

    # Assert
    assert score == pytest.approx(1.05)
    assert status == "supported"
    floor, ceiling = CLAIM_SCORE_SCALE
    assert floor < score < ceiling


def test_score_can_fall_outside_the_band_scale():
    # Arrange — four confident contradictions. The scale bottoms out at -1.0, but
    # the score keeps going; the bar clamps its marker, the number never does.
    events = [FakeEvent("contradicts", 0.95) for _ in range(4)]

    # Act
    score = compute_claim_score(events)

    # Assert
    assert score == pytest.approx(-3.8)
    assert score < CLAIM_SCORE_SCALE[0]
    assert compute_claim_status(events) == "broken"


def test_scale_is_derived_from_the_threshold_table():
    # The UI draws its bar between these two points, so they must track the bands
    # rather than being a second copy of them.
    assert CLAIM_SCORE_SCALE == (
        CLAIM_STATUS_THRESHOLDS[-1][0],
        CLAIM_STATUS_THRESHOLDS[0][0],
    )
