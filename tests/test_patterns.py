import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.domain.pattern import PatternData
from backend.models.base import Base
from backend.models.thesis import Thesis
from backend.models.user import User
from backend.repositories import pattern_repository, post_mortem_repository
from backend.services.pattern_service import (
    MINIMUM_POST_MORTEMS,
    generate_patterns,
    pattern_is_grounded,
)


class FakeProvider:
    """Returns canned patterns and records whether it was called at all."""

    def __init__(self, patterns: list[PatternData] | None = None):
        self._patterns = patterns or []
        self.calls = 0

    def generate_patterns(self, post_mortems: list[dict]) -> list[PatternData]:
        self.calls += 1
        self.last_payload = post_mortems
        return self._patterns


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
def thesis(db):
    user = User(email="demo@local")
    db.add(user)
    db.flush()
    thesis = Thesis(user_id=user.id, ticker="NVDA", reasoning_raw="...", status="breaking")
    db.add(thesis)
    db.commit()
    return thesis


def _answered(db, thesis, count: int) -> list[str]:
    """`count` answered post-mortems; returns their ids."""
    ids = []
    for index in range(count):
        created = post_mortem_repository.create_post_mortem(
            db, thesis_id=thesis.id, user_id=thesis.user_id,
            broken_claim_id=None, status_at_break="breaking",
        )
        post_mortem_repository.answer_post_mortem(
            db, created.id, thesis.user_id, f"Reflection number {index}."
        )
        ids.append(created.id)
    return ids


# --- the minimum-data rule --------------------------------------------------------


def test_below_the_minimum_returns_nothing_and_never_calls_the_ai(db, thesis):
    # Arrange — one short of the threshold.
    _answered(db, thesis, MINIMUM_POST_MORTEMS - 1)
    provider = FakeProvider([PatternData(statement="x", source_post_mortem_ids=["a", "b"])])

    # Act
    result = generate_patterns(db, thesis.user_id, provider=provider)

    # Assert — an AI asked to find patterns in two data points always finds some, so
    # it is never asked.
    assert result == []
    assert provider.calls == 0


def test_unanswered_post_mortems_do_not_count_towards_the_minimum(db, thesis):
    # Arrange — enough rows, but only pending ones have nothing to analyse.
    _answered(db, thesis, MINIMUM_POST_MORTEMS - 1)
    for _ in range(3):
        post_mortem_repository.create_post_mortem(
            db, thesis_id=thesis.id, user_id=thesis.user_id,
            broken_claim_id=None, status_at_break="breaking",
        )
    provider = FakeProvider()

    # Act
    result = generate_patterns(db, thesis.user_id, provider=provider)

    # Assert
    assert result == []
    assert provider.calls == 0


def test_only_answered_post_mortems_are_sent_to_the_provider(db, thesis):
    # Arrange
    answered_ids = _answered(db, thesis, MINIMUM_POST_MORTEMS)
    post_mortem_repository.create_post_mortem(
        db, thesis_id=thesis.id, user_id=thesis.user_id,
        broken_claim_id=None, status_at_break="breaking",
    )
    provider = FakeProvider()

    # Act
    generate_patterns(db, thesis.user_id, provider=provider)

    # Assert
    sent = {item["post_mortem_id"] for item in provider.last_payload}
    assert sent == set(answered_ids)


# --- citation validation ----------------------------------------------------------


def test_pattern_citing_an_unsupplied_id_is_rejected(db, thesis):
    # Arrange — one real id and one the model invented.
    ids = _answered(db, thesis, MINIMUM_POST_MORTEMS)
    provider = FakeProvider(
        [
            PatternData(
                statement="You trust guidance without checking.",
                source_post_mortem_ids=[ids[0], "invented-id-that-was-never-supplied"],
            )
        ]
    )

    # Act
    result = generate_patterns(db, thesis.user_id, provider=provider)

    # Assert — an observation about a person built on invented evidence is never shown.
    assert result == []
    assert pattern_repository.list_patterns(db, thesis.user_id) == []


def test_pattern_citing_only_one_id_is_rejected(db, thesis):
    # Arrange — one reflection is an anecdote, not a pattern.
    ids = _answered(db, thesis, MINIMUM_POST_MORTEMS)
    provider = FakeProvider(
        [PatternData(statement="A one-off observation.", source_post_mortem_ids=[ids[0]])]
    )

    # Act
    result = generate_patterns(db, thesis.user_id, provider=provider)

    # Assert
    assert result == []


def test_pattern_citing_the_same_id_twice_is_rejected(db, thesis):
    # Arrange — two citations that are really one reflection.
    ids = _answered(db, thesis, MINIMUM_POST_MORTEMS)
    provider = FakeProvider(
        [
            PatternData(
                statement="Padded citations.",
                source_post_mortem_ids=[ids[0], ids[0]],
            )
        ]
    )

    # Act
    result = generate_patterns(db, thesis.user_id, provider=provider)

    # Assert
    assert result == []


def test_a_valid_pattern_is_saved_with_its_source_ids(db, thesis):
    # Arrange
    ids = _answered(db, thesis, MINIMUM_POST_MORTEMS)
    statement = "Three of these reflections mention trusting management guidance."
    provider = FakeProvider(
        [PatternData(statement=statement, source_post_mortem_ids=[ids[0], ids[1]])]
    )

    # Act
    result = generate_patterns(db, thesis.user_id, provider=provider)

    # Assert
    assert len(result) == 1
    assert result[0].statement == statement
    assert result[0].evidence_post_mortem_ids == sorted([ids[0], ids[1]])


def test_valid_patterns_survive_alongside_rejected_ones(db, thesis):
    # Arrange — one good, one fabricated. The good one must not be lost.
    ids = _answered(db, thesis, MINIMUM_POST_MORTEMS)
    provider = FakeProvider(
        [
            PatternData(statement="Fabricated.", source_post_mortem_ids=["nope", "also-nope"]),
            PatternData(statement="Genuine.", source_post_mortem_ids=[ids[0], ids[1]]),
        ]
    )

    # Act
    result = generate_patterns(db, thesis.user_id, provider=provider)

    # Assert
    assert [pattern.statement for pattern in result] == ["Genuine."]


def test_pattern_is_grounded_checks_membership_and_count():
    # Arrange
    supplied = {"a", "b", "c"}

    # Act / Assert
    assert pattern_is_grounded(["a", "b"], supplied) is True
    assert pattern_is_grounded(["a"], supplied) is False  # too few
    assert pattern_is_grounded(["a", "z"], supplied) is False  # unknown id
    assert pattern_is_grounded([], supplied) is False


# --- regeneration and lifecycle ---------------------------------------------------


def test_regeneration_replaces_rather_than_appends(db, thesis):
    # Arrange
    ids = _answered(db, thesis, MINIMUM_POST_MORTEMS)
    first = FakeProvider(
        [PatternData(statement="First run.", source_post_mortem_ids=[ids[0], ids[1]])]
    )
    generate_patterns(db, thesis.user_id, provider=first)

    second = FakeProvider(
        [PatternData(statement="Second run.", source_post_mortem_ids=[ids[1], ids[2]])]
    )

    # Act
    generate_patterns(db, thesis.user_id, provider=second)

    # Assert — one current set, not an accumulating history.
    stored = pattern_repository.list_patterns(db, thesis.user_id)
    assert [pattern.statement for pattern in stored] == ["Second run."]


def test_an_empty_list_from_the_provider_is_handled_cleanly(db, thesis):
    # Arrange — finding nothing is a valid, expected answer.
    ids = _answered(db, thesis, MINIMUM_POST_MORTEMS)
    generate_patterns(
        db,
        thesis.user_id,
        provider=FakeProvider(
            [PatternData(statement="Stale.", source_post_mortem_ids=[ids[0], ids[1]])]
        ),
    )
    provider = FakeProvider([])

    # Act
    result = generate_patterns(db, thesis.user_id, provider=provider)

    # Assert — no error, and the stale pattern is cleared rather than left standing.
    assert result == []
    assert pattern_repository.list_patterns(db, thesis.user_id) == []
    assert provider.calls == 1


def test_dismissed_patterns_are_excluded_from_the_list(db, thesis):
    # Arrange
    ids = _answered(db, thesis, MINIMUM_POST_MORTEMS)
    generate_patterns(
        db,
        thesis.user_id,
        provider=FakeProvider(
            [
                PatternData(statement="Kept.", source_post_mortem_ids=[ids[0], ids[1]]),
                PatternData(statement="Dismissed.", source_post_mortem_ids=[ids[1], ids[2]]),
            ]
        ),
    )
    to_dismiss = next(
        pattern
        for pattern in pattern_repository.list_patterns(db, thesis.user_id)
        if pattern.statement == "Dismissed."
    )

    # Act
    pattern_repository.dismiss_pattern(db, to_dismiss.id, thesis.user_id)

    # Assert
    visible = pattern_repository.list_patterns(db, thesis.user_id)
    assert [pattern.statement for pattern in visible] == ["Kept."]
    assert len(pattern_repository.list_patterns(db, thesis.user_id, include_dismissed=True)) == 2


def test_dismissing_a_missing_pattern_returns_none(db, thesis):
    # Arrange / Act / Assert
    assert pattern_repository.dismiss_pattern(db, "no-such-id", thesis.user_id) is None
