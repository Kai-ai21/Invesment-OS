import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.models.base import Base
from backend.models.claim import Claim
from backend.models.document import Document
from backend.models.evidence_event import EvidenceEvent
from backend.models.thesis import Thesis
from backend.models.user import User
from backend.repositories import post_mortem_repository
from backend.services.post_mortem_service import (
    PostMortemError,
    PostMortemNotFound,
    generate_question,
    question_is_grounded,
)

REASONING = "I think margins hold because competitors cannot match the high-end chips."
CLAIM_STATEMENT = "Nvidia sustains high gross margins."
CONTRADICTING_QUOTE = "Gross margins decreased to 71.1% in fiscal year 2026."
# Plausible-sounding but supplied to nobody — the model inventing this is the exact
# failure the grounding check exists to catch.
FABRICATED_QUOTE = "Margins collapsed to 43.2% amid an aggressive price war."


class FakeProvider:
    """Returns canned questions in order, recording how many times it was called."""

    def __init__(self, questions: list[str]):
        self._questions = list(questions)
        self.calls = 0

    def generate_reflection_question(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        # Repeat the final answer if asked more times than we were given questions.
        return self._questions[min(self.calls - 1, len(self._questions) - 1)]


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def post_mortem(db):
    """A post-mortem on a broken core claim, with one contradicting evidence quote."""
    user = User(email="demo@local")
    db.add(user)
    db.flush()
    thesis = Thesis(
        user_id=user.id, ticker="NVDA", reasoning_raw=REASONING, status="breaking"
    )
    db.add(thesis)
    db.flush()
    claim = Claim(
        thesis_id=thesis.id,
        statement=CLAIM_STATEMENT,
        proof_condition="Gross margin stays at or above 72 percent.",
        break_condition="Gross margin falls below 65 percent.",
        is_core=True,
        status="broken",
    )
    db.add(claim)
    db.flush()
    document = Document(
        source_type="paste",
        title="10-K",
        content_hash="hash-1",
        raw_text=CONTRADICTING_QUOTE,
    )
    db.add(document)
    db.flush()
    db.add_all(
        [
            EvidenceEvent(
                claim_id=claim.id,
                document_id=document.id,
                verdict="contradicts",
                confidence=0.9,
                evidence_quote=CONTRADICTING_QUOTE,
                reasoning="Below the break condition.",
            ),
            # A "supports" event must NOT be offered as contradicting evidence.
            EvidenceEvent(
                claim_id=claim.id,
                document_id=document.id,
                verdict="supports",
                confidence=0.5,
                evidence_quote="Margins remained healthy earlier in the year.",
                reasoning="Above the proof threshold at the time.",
            ),
        ]
    )
    db.commit()
    return post_mortem_repository.create_post_mortem(
        db, thesis_id=thesis.id, broken_claim_id=claim.id, status_at_break="breaking"
    )


# --- the grounding check ----------------------------------------------------------


def test_question_quoting_only_supplied_material_is_grounded():
    # Arrange
    source = [REASONING, CLAIM_STATEMENT, CONTRADICTING_QUOTE]
    question = (
        f'The filing reported "{CONTRADICTING_QUOTE}" '
        "What made you confident margins would hold?"
    )

    # Act / Assert
    assert question_is_grounded(question, source) is True


def test_question_with_curly_quotes_is_still_checked():
    # Arrange — models emit smart quotes constantly; if the regex missed them the
    # check would silently pass every fabrication.
    source = [CLAIM_STATEMENT, CONTRADICTING_QUOTE]
    fabricated = f"The filing reported “{FABRICATED_QUOTE}” What made you confident?"

    # Act / Assert
    assert question_is_grounded(fabricated, source) is False


def test_question_quoting_the_investors_own_words_is_grounded():
    # Arrange — the reasoning was supplied to the model, so quoting it back is not
    # invention.
    source = [REASONING, CLAIM_STATEMENT]
    question = 'You wrote "competitors cannot match the high-end chips". What supported that?'

    # Act / Assert
    assert question_is_grounded(question, source) is True


def test_question_with_no_quotes_is_grounded():
    # Arrange — paraphrase outside quotation marks is allowed.
    source = [CLAIM_STATEMENT]
    question = "Margins fell below what you expected. What made you confident they would hold?"

    # Act / Assert
    assert question_is_grounded(question, source) is True


def test_grounding_ignores_casing_and_whitespace_differences():
    # Arrange
    source = [CONTRADICTING_QUOTE]
    question = 'It said "GROSS   MARGINS   DECREASED to 71.1% in fiscal year 2026." Why?'

    # Act / Assert
    assert question_is_grounded(question, source) is True


# --- generation -------------------------------------------------------------------


def test_grounded_question_is_accepted_and_stored(db, post_mortem):
    # Arrange
    good = (
        f'The filing reported "{CONTRADICTING_QUOTE}" '
        "What made you confident margins would hold above 72 percent?"
    )
    provider = FakeProvider([good])

    # Act
    result = generate_question(db, post_mortem.id, provider=provider)

    # Assert
    assert result.prompt_question == good
    assert provider.calls == 1  # accepted first time, no retry


def test_only_contradicting_evidence_is_offered_to_the_model(db, post_mortem):
    # Arrange
    provider = FakeProvider(["Margins fell. What made you confident?"])

    # Act
    generate_question(db, post_mortem.id, provider=provider)

    # Assert — the "supports" quote must not be presented as what broke the claim.
    quotes = provider.last_kwargs["evidence_quotes"]
    assert quotes == [CONTRADICTING_QUOTE]


def test_ungrounded_question_is_rejected_retried_then_falls_back(db, post_mortem):
    # Arrange — the model invents a figure twice.
    fabricated = f'The filing said "{FABRICATED_QUOTE}" What made you confident?'
    provider = FakeProvider([fabricated, fabricated])

    # Act
    result = generate_question(db, post_mortem.id, provider=provider)

    # Assert — retried once, then stored the safe fallback rather than a fabrication.
    assert provider.calls == 2
    assert FABRICATED_QUOTE not in result.prompt_question
    assert "43.2%" not in result.prompt_question


def test_fallback_contains_the_claim_statement_verbatim(db, post_mortem):
    # Arrange
    fabricated = f'The filing said "{FABRICATED_QUOTE}" What made you confident?'
    provider = FakeProvider([fabricated, fabricated])

    # Act
    result = generate_question(db, post_mortem.id, provider=provider)

    # Assert
    assert CLAIM_STATEMENT in result.prompt_question


def test_a_retry_that_succeeds_is_used(db, post_mortem):
    # Arrange — bad first, good second.
    fabricated = f'The filing said "{FABRICATED_QUOTE}" What made you confident?'
    good = f'The filing reported "{CONTRADICTING_QUOTE}" What made you confident?'
    provider = FakeProvider([fabricated, good])

    # Act
    result = generate_question(db, post_mortem.id, provider=provider)

    # Assert
    assert provider.calls == 2
    assert result.prompt_question == good


# --- idempotence ------------------------------------------------------------------


def test_generating_twice_does_not_overwrite_an_existing_question(db, post_mortem):
    # Arrange
    first = f'The filing reported "{CONTRADICTING_QUOTE}" What made you confident?'
    provider = FakeProvider([first])
    generate_question(db, post_mortem.id, provider=provider)

    second_provider = FakeProvider(["A completely different question?"])

    # Act — the frontend may call this every time it displays the post-mortem.
    result = generate_question(db, post_mortem.id, provider=second_provider)

    # Assert — no second call, no reworded question under the user.
    assert second_provider.calls == 0
    assert result.prompt_question == first


def test_force_regenerates_the_question(db, post_mortem):
    # Arrange
    first = f'The filing reported "{CONTRADICTING_QUOTE}" What made you confident?'
    generate_question(db, post_mortem.id, provider=FakeProvider([first]))

    replacement = f'Margins moved: "{CONTRADICTING_QUOTE}" What were you reading then?'
    provider = FakeProvider([replacement])

    # Act
    result = generate_question(db, post_mortem.id, provider=provider, force=True)

    # Assert
    assert provider.calls == 1
    assert result.prompt_question == replacement


# --- error paths ------------------------------------------------------------------


def test_missing_post_mortem_raises_not_found(db):
    # Arrange / Act / Assert
    with pytest.raises(PostMortemNotFound):
        generate_question(db, "no-such-id", provider=FakeProvider(["x"]))


def test_post_mortem_without_a_broken_claim_cannot_be_asked_about(db):
    # Arrange — a manually opened post-mortem on a thesis with no broken core claim.
    user = User(email="demo@local")
    db.add(user)
    db.flush()
    thesis = Thesis(
        user_id=user.id, ticker="AAPL", reasoning_raw=REASONING, status="weakening"
    )
    db.add(thesis)
    db.flush()
    db.commit()
    created = post_mortem_repository.create_post_mortem(
        db, thesis_id=thesis.id, broken_claim_id=None, status_at_break="weakening"
    )
    provider = FakeProvider(["should never be called"])

    # Act / Assert — a generic question is worse than none, so this refuses rather
    # than inventing one.
    with pytest.raises(PostMortemError):
        generate_question(db, created.id, provider=provider)
    assert provider.calls == 0
