import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.models.base import Base
from backend.models.claim import Claim
from backend.models.evidence_event import EvidenceEvent
from backend.models.document import Document
from backend.models.thesis import Thesis
from backend.models.user import User
from backend.repositories import post_mortem_repository
from backend.services.verification_service import recompute_thesis


@pytest.fixture
def db():
    # In-memory SQLite shared across connections, so the service's commits are visible.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def thesis(db):
    """A thesis with one CORE claim, starting healthy."""
    user = User(email="demo@local")
    db.add(user)
    db.flush()
    thesis = Thesis(user_id=user.id, ticker="NVDA", reasoning_raw="...", status="pending")
    db.add(thesis)
    db.flush()
    db.add(
        Claim(
            thesis_id=thesis.id,
            statement="Nvidia sustains high gross margins.",
            proof_condition="Gross margin stays at or above 72 percent.",
            break_condition="Gross margin falls below 65 percent.",
            is_core=True,
            status="pending",
        )
    )
    db.commit()
    return thesis


def _break_the_core_claim(db, thesis) -> None:
    """Attach contradicting evidence so the core claim scores as broken.

    Real evidence rows rather than a hand-set status, because recompute_thesis
    recalculates every claim from its evidence — a status written directly would just
    be overwritten.
    """
    document = Document(
        source_type="paste",
        title="Bad news",
        content_hash=f"hash-{thesis.id}-{db.query(Document).count()}",
        raw_text="Gross margin collapsed.",
    )
    db.add(document)
    db.flush()
    claim = thesis.claims[0]
    # Two high-confidence contradictions push the score below the "broken" band.
    for _ in range(2):
        db.add(
            EvidenceEvent(
                claim_id=claim.id,
                document_id=document.id,
                verdict="contradicts",
                confidence=0.95,
                evidence_quote="Gross margin collapsed.",
                reasoning="Below the break condition.",
            )
        )
    db.commit()


# --- the trigger ------------------------------------------------------------------


def test_thesis_transitioning_to_breaking_creates_a_pending_post_mortem(db, thesis):
    # Arrange
    _break_the_core_claim(db, thesis)

    # Act
    prev_status, new_status = recompute_thesis(db, thesis.id, thesis.user_id)

    # Assert
    assert (prev_status, new_status) == ("pending", "breaking")
    post_mortems = post_mortem_repository.list_post_mortems(db, thesis.user_id, thesis_id=thesis.id)
    assert len(post_mortems) == 1
    created = post_mortems[0]
    assert created.user_response is None  # pending
    assert created.answered_at is None
    assert created.prompt_question is None  # the AI writes this in Step 2
    assert created.status_at_break == "breaking"
    assert created.broken_claim_id == thesis.claims[0].id


def test_thesis_already_breaking_does_not_create_a_second_post_mortem(db, thesis):
    # Arrange — first transition into "breaking" opens one.
    _break_the_core_claim(db, thesis)
    recompute_thesis(db, thesis.id, thesis.user_id)
    assert len(post_mortem_repository.list_post_mortems(db, thesis.user_id, thesis_id=thesis.id)) == 1

    # Act — recomputing again while ALREADY breaking is not a new transition.
    prev_status, new_status = recompute_thesis(db, thesis.id, thesis.user_id)

    # Assert
    assert (prev_status, new_status) == ("breaking", "breaking")
    assert len(post_mortem_repository.list_post_mortems(db, thesis.user_id, thesis_id=thesis.id)) == 1


def test_thesis_with_an_unanswered_post_mortem_does_not_get_another(db, thesis):
    # Arrange — an open post-mortem already exists, and the thesis is not yet breaking
    # so the transition guard alone would NOT stop a second one.
    post_mortem_repository.create_post_mortem(
        db, thesis_id=thesis.id, user_id=thesis.user_id,
        broken_claim_id=None, status_at_break="weakening"
    )
    _break_the_core_claim(db, thesis)

    # Act
    recompute_thesis(db, thesis.id, thesis.user_id)

    # Assert — the pending-duplicate guard held.
    assert len(post_mortem_repository.list_post_mortems(db, thesis.user_id, thesis_id=thesis.id)) == 1


def test_a_failure_creating_the_post_mortem_does_not_break_verification(
    db, thesis, monkeypatch
):
    # Arrange — saving evidence is the primary job; a reflection prompt is secondary.
    def explode(*args, **kwargs):
        raise RuntimeError("post-mortem storage is down")

    monkeypatch.setattr(post_mortem_repository, "create_post_mortem", explode)
    _break_the_core_claim(db, thesis)

    # Act — must not raise.
    prev_status, new_status = recompute_thesis(db, thesis.id, thesis.user_id)

    # Assert — the status change still landed and was still persisted.
    assert (prev_status, new_status) == ("pending", "breaking")
    db.refresh(thesis)
    assert thesis.status == "breaking"


# --- the repository ---------------------------------------------------------------


def test_answering_sets_the_response_and_the_answered_timestamp(db, thesis):
    # Arrange
    created = post_mortem_repository.create_post_mortem(
        db, thesis_id=thesis.id, user_id=thesis.user_id,
        broken_claim_id=None, status_at_break="breaking"
    )

    # Act
    answered = post_mortem_repository.answer_post_mortem(
        db, created.id, thesis.user_id, "I anchored on one quarter of data."
    )

    # Assert
    assert answered is not None
    assert answered.user_response == "I anchored on one quarter of data."
    assert answered.answered_at is not None


def test_answering_a_missing_post_mortem_returns_none(db, thesis):
    # Arrange / Act / Assert
    assert post_mortem_repository.answer_post_mortem(db, "no-such-id", thesis.user_id, "text") is None


def test_answered_post_mortems_are_excluded_from_pending_only(db, thesis):
    # Arrange
    pending = post_mortem_repository.create_post_mortem(
        db, thesis_id=thesis.id, user_id=thesis.user_id,
        broken_claim_id=None, status_at_break="breaking"
    )
    answered = post_mortem_repository.create_post_mortem(
        db, thesis_id=thesis.id, user_id=thesis.user_id,
        broken_claim_id=None, status_at_break="breaking"
    )
    post_mortem_repository.answer_post_mortem(db, answered.id, thesis.user_id, "Answered.")

    # Act
    open_ones = post_mortem_repository.list_post_mortems(db, thesis.user_id, pending_only=True)

    # Assert
    assert [item.id for item in open_ones] == [pending.id]


def test_deleting_a_post_mortem_works_and_is_reported(db, thesis):
    # Arrange — deletable by design, unlike evidence events.
    created = post_mortem_repository.create_post_mortem(
        db, thesis_id=thesis.id, user_id=thesis.user_id,
        broken_claim_id=None, status_at_break="breaking"
    )

    # Act
    deleted = post_mortem_repository.delete_post_mortem(db, created.id, thesis.user_id)

    # Assert
    assert deleted is True
    assert post_mortem_repository.get_post_mortem(db, created.id, thesis.user_id) is None


def test_deleting_a_missing_post_mortem_returns_false(db, thesis):
    # Arrange / Act / Assert
    assert post_mortem_repository.delete_post_mortem(db, "no-such-id", thesis.user_id) is False


def test_count_answered_ignores_pending_ones(db, thesis):
    # Arrange
    post_mortem_repository.create_post_mortem(
        db, thesis_id=thesis.id, user_id=thesis.user_id,
        broken_claim_id=None, status_at_break="breaking"
    )
    answered = post_mortem_repository.create_post_mortem(
        db, thesis_id=thesis.id, user_id=thesis.user_id,
        broken_claim_id=None, status_at_break="breaking"
    )

    # Act / Assert — still 0 while it is only pending.
    assert post_mortem_repository.count_answered(db, thesis.user_id) == 0
    post_mortem_repository.answer_post_mortem(
        db, answered.id, thesis.user_id, "Because I over-anchored."
    )
    assert post_mortem_repository.count_answered(db, thesis.user_id) == 1


def test_denormalised_fields_are_reachable_for_the_api(db, thesis):
    # Arrange — PostMortemOut reads these, so the frontend needn't join.
    created = post_mortem_repository.create_post_mortem(
        db,
        thesis_id=thesis.id,
        user_id=thesis.user_id,
        broken_claim_id=thesis.claims[0].id,
        status_at_break="breaking",
    )

    # Act
    fetched = post_mortem_repository.get_post_mortem(db, created.id, thesis.user_id)

    # Assert
    assert fetched is not None
    assert fetched.ticker == "NVDA"
    assert fetched.broken_claim_statement == "Nvidia sustains high gross margins."


def test_broken_claim_statement_is_none_when_no_claim_is_linked(db, thesis):
    # Arrange — a manually requested post-mortem has no specific claim.
    created = post_mortem_repository.create_post_mortem(
        db, thesis_id=thesis.id, user_id=thesis.user_id,
        broken_claim_id=None, status_at_break="weakening"
    )

    # Act
    fetched = post_mortem_repository.get_post_mortem(db, created.id, thesis.user_id)

    # Assert
    assert fetched is not None
    assert fetched.broken_claim_statement is None
