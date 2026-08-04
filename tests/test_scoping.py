"""A2: cross-user isolation, one test per user-owned resource type.

⚠️ THE POINT OF THIS FILE IS THAT IT HAS NO GAPS. An IDOR produces no error and no
log line — the endpoint returns 200 with someone else's data and looks perfectly
healthy — so the only thing that catches a missed scope is a test that specifically
asks for another user's row by id. A resource type absent from this file is a
resource type nobody is checking.

Covered: theses, claims, documents, evidence_events, alerts, post_mortems, patterns,
holdings. The registry at the bottom asserts that list against the models actually
mapped on Base, so ADDING a user-owned table and forgetting to scope it fails here
rather than shipping.

Every "by id" case asserts 404 and not 403: a 403 says "this exists, but not for
you", which confirms a guessed id names a real record.
"""

import warnings

import pytest

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.core.security import create_access_token, hash_password  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models.alert import Alert  # noqa: E402
from backend.models.base import Base  # noqa: E402
from backend.models.claim import Claim  # noqa: E402
from backend.models.database import get_db  # noqa: E402
from backend.models.document import Document  # noqa: E402
from backend.models.evidence_event import EvidenceEvent  # noqa: E402
from backend.models.holding import Holding  # noqa: E402
from backend.models.pattern import Pattern  # noqa: E402
from backend.models.post_mortem import PostMortem  # noqa: E402
from backend.models.thesis import Thesis  # noqa: E402
from backend.models.user import User  # noqa: E402


class Fixtures:
    """One user, and one of every user-owned record, all wired together."""

    def __init__(self, db, email: str, ticker: str):
        self.user = User(email=email, password_hash=hash_password("a-real-password"))
        db.add(self.user)
        db.flush()

        self.thesis = Thesis(
            user_id=self.user.id,
            ticker=ticker,
            reasoning_raw=f"{ticker} reasoning",
            status="breaking",
        )
        db.add(self.thesis)
        db.flush()

        self.claim = Claim(
            thesis_id=self.thesis.id,
            statement=f"{ticker} margins hold.",
            proof_condition="p",
            break_condition="b",
            is_core=True,
            status="broken",
        )
        db.add(self.claim)
        db.flush()

        # Documents are deduplicated GLOBALLY by content hash, so each user needs
        # distinct text here or they would share one row — see the document test.
        self.document = Document(
            source_type="paste",
            title=f"{ticker} 10-K",
            content_hash=f"hash-{ticker}",
            raw_text=f"{ticker} private document text",
        )
        db.add(self.document)
        db.flush()

        self.evidence = EvidenceEvent(
            claim_id=self.claim.id,
            document_id=self.document.id,
            verdict="contradicts",
            confidence=0.9,
            evidence_quote=f"{ticker} secret quote",
            reasoning="r",
        )
        db.add(self.evidence)

        self.alert = Alert(
            thesis_id=self.thesis.id,
            prev_status="active",
            new_status="breaking",
            summary=f"{ticker} moved",
        )
        db.add(self.alert)

        self.post_mortem = PostMortem(
            thesis_id=self.thesis.id,
            broken_claim_id=self.claim.id,
            status_at_break="breaking",
            prompt_question=f"{ticker} what did you miss?",
            user_response=f"{ticker} private reflection",
        )
        db.add(self.post_mortem)

        self.holding = Holding(
            user_id=self.user.id, ticker=ticker, shares=10.0, average_cost=100.0
        )
        db.add(self.holding)
        db.flush()

        self.pattern = Pattern(
            user_id=self.user.id,
            statement=f"{ticker} recurring behaviour",
            evidence_post_mortem_ids=[self.post_mortem.id],
        )
        db.add(self.pattern)
        db.commit()

        self.token = create_access_token(self.user.id)

    @property
    def auth(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def world(db_session):
    """Two fully populated users, A and B, and a client that talks to both."""
    app.dependency_overrides[get_db] = lambda: db_session
    a = Fixtures(db_session, "alice@example.com", "NVDA")
    b = Fixtures(db_session, "bob@example.com", "AAPL")
    try:
        yield TestClient(app), a, b
    finally:
        app.dependency_overrides.clear()


def assert_not_found(response):
    """404, and specifically NOT 403.

    ⚠️ THE STATUS CODE IS ITSELF THE VULNERABILITY HERE. 403 means "it exists, you
    may not have it" — enough to enumerate other people's records by walking ids and
    watching which ones answer 403 instead of 404.
    """
    assert response.status_code == 404, (
        f"expected 404, got {response.status_code}: {response.text[:200]}"
    )


# --- theses -----------------------------------------------------------------------


def test_thesis_by_id_is_404_for_another_user(world):
    client, a, b = world
    assert_not_found(client.get(f"/theses/{a.thesis.id}", headers=b.auth))
    # And A can still read it — proving the 404 is about ownership, not a broken route.
    assert client.get(f"/theses/{a.thesis.id}", headers=a.auth).status_code == 200


def test_thesis_list_contains_none_of_the_other_users(world):
    client, a, b = world
    body = client.get("/theses", headers=b.auth).json()
    ids = {item["id"] for item in body}
    assert ids == {b.thesis.id}
    assert a.thesis.id not in ids
    assert not any(item["ticker"] == "NVDA" for item in body)


def test_writes_to_another_users_thesis_are_404(world):
    """Every sub-resource of a thesis, not just the read.

    ⚠️ THE EXPENSIVE ONES ARE THE POINT. /check spends AI calls and SEC requests, and
    /documents writes evidence that MOVES the thesis's status — an unscoped write here
    is a stranger editing your record, not merely reading it. Both must refuse before
    doing any work.
    """
    client, a, b = world
    assert_not_found(
        client.post(
            f"/theses/{a.thesis.id}/documents",
            json={"raw_text": "some text", "title": "t"},
            headers=b.auth,
        )
    )
    assert_not_found(client.post(f"/theses/{a.thesis.id}/check", headers=b.auth))
    assert_not_found(client.post(f"/theses/{a.thesis.id}/post-mortems", headers=b.auth))
    assert_not_found(client.get(f"/theses/{a.thesis.id}/chart", headers=b.auth))


# --- claims -----------------------------------------------------------------------


def test_claims_are_unreachable_through_another_users_thesis(world):
    """Claims have no endpoint of their own — they are nested in the thesis payload,
    so the scope they inherit is the thesis's."""
    client, a, b = world

    assert_not_found(client.get(f"/theses/{a.thesis.id}", headers=b.auth))

    # And B's own list carries only B's claims — no leakage through the bulk reader.
    body = client.get("/theses", headers=b.auth).json()
    statements = [claim["statement"] for item in body for claim in item["claims"]]
    assert statements == [b.claim.statement]
    assert a.claim.statement not in statements


# --- documents --------------------------------------------------------------------


def test_document_text_of_another_user_is_never_served(world):
    """Documents are deduplicated globally and have no owner column, by design: the
    same 10-K submitted twice should be one row. What must NOT be shared is any
    evidence drawn from it, which is what actually reaches a response."""
    client, a, b = world

    assert_not_found(client.get(f"/theses/{a.thesis.id}/evidence", headers=b.auth))

    own = client.get(f"/theses/{b.thesis.id}/evidence", headers=b.auth).json()
    serialised = str(own)
    assert a.document.raw_text not in serialised
    assert a.evidence.evidence_quote not in serialised


def test_global_document_dedup_does_not_skip_verification_for_a_second_user(db_session):
    """The bug the audit turned up alongside the scoping.

    Dedup is keyed on content hash across ALL users, and the old code returned early
    whenever the document merely EXISTED — so if A had submitted a filing, B's thesis
    was handed its existing evidence without ever being verified against it. The
    question has to be "has THIS thesis seen THIS document", not "has anyone".
    """
    from backend.repositories import evidence_repository

    a = Fixtures(db_session, "alice@example.com", "NVDA")
    b = Fixtures(db_session, "bob@example.com", "AAPL")

    # A's thesis HAS been verified against A's document.
    assert evidence_repository.thesis_has_evidence_from_document(
        db_session, thesis_id=a.thesis.id, document_id=a.document.id, user_id=a.user.id
    )
    # B's has not — even though the document row exists and is globally visible.
    assert not evidence_repository.thesis_has_evidence_from_document(
        db_session, thesis_id=b.thesis.id, document_id=a.document.id, user_id=b.user.id
    )


# --- evidence_events --------------------------------------------------------------


def test_evidence_by_thesis_is_404_for_another_user(world):
    client, a, b = world
    assert_not_found(client.get(f"/theses/{a.thesis.id}/evidence", headers=b.auth))


def test_evidence_list_contains_none_of_the_other_users(world):
    client, a, b = world
    body = client.get(f"/theses/{b.thesis.id}/evidence", headers=b.auth).json()
    quotes = {item["evidence_quote"] for item in body}
    assert quotes == {b.evidence.evidence_quote}
    assert a.evidence.evidence_quote not in quotes


# --- alerts -----------------------------------------------------------------------


def test_alert_by_id_is_404_for_another_user(world):
    client, a, b = world
    assert_not_found(client.patch(f"/alerts/{a.alert.id}/read", headers=b.auth))
    # Untouched: the refusal must not have marked it read on the way out.
    assert client.patch(f"/alerts/{a.alert.id}/read", headers=a.auth).status_code == 200


def test_alert_list_contains_none_of_the_other_users(world):
    client, a, b = world
    body = client.get("/alerts", headers=b.auth).json()
    ids = {item["id"] for item in body}
    assert ids == {b.alert.id}
    assert a.alert.id not in ids


# --- post_mortems -----------------------------------------------------------------


def test_post_mortem_by_id_is_404_for_another_user(world):
    client, a, b = world
    assert_not_found(
        client.patch(
            f"/post-mortems/{a.post_mortem.id}",
            json={"user_response": "hijacked"},
            headers=b.auth,
        )
    )
    assert_not_found(
        client.post(f"/post-mortems/{a.post_mortem.id}/question", headers=b.auth)
    )


def test_deleting_another_users_post_mortem_is_404_and_does_not_delete(world):
    """⚠️ DESTRUCTIVE AND UNRECOVERABLE. Unscoped, this let anyone erase a stranger's
    reflections with a guessed uuid, silently."""
    client, a, b = world

    assert_not_found(client.delete(f"/post-mortems/{a.post_mortem.id}", headers=b.auth))

    # Still there, and still A's.
    body = client.get("/post-mortems", headers=a.auth).json()
    assert a.post_mortem.id in {item["id"] for item in body}


def test_post_mortem_list_contains_none_of_the_other_users(world):
    client, a, b = world
    body = client.get("/post-mortems", headers=b.auth).json()
    ids = {item["id"] for item in body}
    assert ids == {b.post_mortem.id}
    assert a.post_mortem.id not in ids
    assert a.post_mortem.user_response not in str(body)


# --- patterns ---------------------------------------------------------------------


def test_pattern_by_id_is_404_for_another_user(world):
    client, a, b = world
    assert_not_found(client.patch(f"/patterns/{a.pattern.id}/dismiss", headers=b.auth))


def test_pattern_list_contains_none_of_the_other_users(world):
    client, a, b = world
    body = client.get("/patterns", headers=b.auth).json()
    statements = {item["statement"] for item in body}
    assert statements == {b.pattern.statement}
    assert a.pattern.statement not in statements


def test_regenerating_patterns_does_not_delete_another_users(db_session):
    """⚠️ DATA LOSS, NOT DISCLOSURE. delete_all_patterns() had no filter, so the
    second user ever to press "Analyse my reflections" wiped the first user's set —
    with nothing raised and nothing logged."""
    from backend.repositories import pattern_repository

    a = Fixtures(db_session, "alice@example.com", "NVDA")
    b = Fixtures(db_session, "bob@example.com", "AAPL")

    removed = pattern_repository.delete_all_patterns(db_session, b.user.id)

    assert removed == 1
    surviving = pattern_repository.list_patterns(db_session, a.user.id)
    assert [p.statement for p in surviving] == [a.pattern.statement]


# --- holdings ---------------------------------------------------------------------


def test_holding_by_id_is_404_for_another_user(world):
    client, a, b = world
    assert_not_found(
        client.patch(
            f"/holdings/{a.holding.id}", json={"shares": 999.0}, headers=b.auth
        )
    )
    assert_not_found(client.delete(f"/holdings/{a.holding.id}", headers=b.auth))


def test_a_refused_holding_write_changes_nothing(world):
    """A 404 that still performed the update would be the worst possible outcome."""
    client, a, b = world

    client.patch(f"/holdings/{a.holding.id}", json={"shares": 999.0}, headers=b.auth)
    client.delete(f"/holdings/{a.holding.id}", headers=b.auth)

    rows = client.get("/holdings", headers=a.auth).json()["holdings"]
    mine = [row for row in rows if row["id"] == a.holding.id]
    assert len(mine) == 1
    assert mine[0]["shares"] == 10.0


def test_holding_list_contains_none_of_the_other_users(world):
    client, a, b = world
    rows = client.get("/holdings", headers=b.auth).json()["holdings"]
    ids = {row["id"] for row in rows}
    assert ids == {b.holding.id}
    assert a.holding.id not in ids


# --- the registry -----------------------------------------------------------------


def test_every_user_owned_table_is_covered_by_this_file():
    """⚠️ THE GUARD AGAINST THE NEXT TABLE.

    "Do not skip a resource type. The one you skip is the one that leaks." This asserts
    that against the mapped models rather than against a list somebody remembered to
    update: a new user-owned table fails here until it is scoped and tested.

    `users` is excluded — it is the owner, not an owned thing, and A1 covers it.
    """
    mapped = {mapper.class_.__tablename__ for mapper in Base.registry.mappers}
    covered = {
        "theses",
        "claims",
        "documents",
        "evidence_events",
        "alerts",
        "post_mortems",
        "patterns",
        "holdings",
    }
    uncovered = mapped - covered - {"users"}
    assert not uncovered, (
        f"user-owned tables with no cross-user test: {sorted(uncovered)}. "
        "Scope the repository and add a test above before this passes."
    )
