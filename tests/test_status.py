from dataclasses import dataclass

from backend.domain.status import (
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
