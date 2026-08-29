"""Login tracking: what gets counted, what does not, and what it must never break.

The load-bearing tests here are the two negatives — a failed login writes nothing, and
a broken write does not fail the login. Everything else is arithmetic.
"""

import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.security import decode_access_token
from backend.main import app
from backend.models.base import Base
from backend.models.claim import Claim  # noqa: F401 — Thesis.claims cannot resolve without it
from backend.models.database import get_db
from backend.models.login_event import LoginEvent
from backend.models.thesis import Thesis  # noqa: F401 (registers mapper with Base)
from backend.models.user import User
from backend.repositories.login_event_repository import (
    RETENTION_DAYS,
    purge_expired_login_events,
    record_successful_login,
)

EMAIL = "ada@example.com"
PASSWORD = "correct-horse-battery"


@pytest.fixture
def db_session():
    """A private in-memory database per test, as in tests/test_auth.py.

    StaticPool with a shared connection so the request handler and the assertions
    afterwards see the same database.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def account(client):
    """A real account created through the API, so the stored hash is a real one."""
    response = client.post("/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 201
    return response


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


# --- what is counted --------------------------------------------------------------


def test_a_successful_login_records_exactly_one_event(client, account, db_session):
    # Arrange — signup itself must not have counted. Creating an account is not
    # signing into the shared one, and the question being asked is about logins.
    assert db_session.query(LoginEvent).count() == 0
    user = db_session.query(User).one()

    # Act
    response = login(client)

    # Assert — one row, pointing at the account that just authenticated.
    assert response.status_code == 200
    event = db_session.query(LoginEvent).one()
    assert event.user_id == user.id
    assert event.created_at is not None


def test_each_login_adds_one_more_event(client, account, db_session):
    # Act — the count is the whole product, so it is asserted as a count.
    for _ in range(3):
        assert login(client).status_code == 200

    # Assert
    assert db_session.query(LoginEvent).count() == 3


def test_a_wrong_password_records_nothing(client, account, db_session):
    # Act
    response = login(client, password="not-the-password")

    # Assert — refused, and the table is untouched.
    assert response.status_code == 401
    assert db_session.query(LoginEvent).count() == 0


def test_an_unknown_email_records_nothing(client, account, db_session):
    # Act — an address with no account at all, which takes the other branch of the
    # login route (the dummy-hash path that exists for constant time).
    response = login(client, email="nobody@example.com")

    # Assert
    assert response.status_code == 401
    assert db_session.query(LoginEvent).count() == 0


def test_a_locked_account_records_nothing(client, db_session):
    # Arrange — password_hash defaults to the unusable marker, so this account exists
    # and cannot be logged into. It must not produce an event either.
    db_session.add(User(email="locked@example.com"))
    db_session.commit()

    # Act
    response = login(client, email="locked@example.com", password="anything-at-all")

    # Assert
    assert response.status_code == 401
    assert db_session.query(LoginEvent).count() == 0


# --- what is stored ---------------------------------------------------------------


def test_an_event_stores_nothing_but_an_id_a_user_and_a_timestamp(client, account, db_session):
    """⚠️ THE PRIVACY TEST. README.md tells people sharing the demo account exactly
    what is kept; a fourth column here would make that statement untrue."""
    # Act
    login(client)

    # Assert — the column set, not just the values, so adding `ip_address` fails here.
    assert {column.name for column in LoginEvent.__table__.columns} == {
        "id",
        "user_id",
        "created_at",
    }

    # And nothing that went into the request came back out on the row.
    row = {
        column.name: str(getattr(db_session.query(LoginEvent).one(), column.name))
        for column in LoginEvent.__table__.columns
    }
    assert not any(PASSWORD in value or EMAIL in value for value in row.values())


# --- tracking must never break authentication -------------------------------------


def test_a_tracking_failure_does_not_prevent_login(client, account, db_session, caplog):
    """⚠️ THE ONE THAT MATTERS. Analytics must not be able to lock anyone out.

    The table is dropped rather than mocked, so the failure is a real database error
    raised from a real flush — the shape of the thing that would actually happen if a
    migration had not been applied, or the table were dropped by hand.
    """
    # Arrange
    db_session.execute(text("DROP TABLE login_events"))
    db_session.commit()

    # Act
    with caplog.at_level(logging.WARNING):
        response = login(client)

    # Assert — the login succeeded, with a usable token, exactly as before.
    assert response.status_code == 200
    user_id = db_session.query(User).one().id
    assert decode_access_token(response.json()["access_token"]) == user_id

    # And the failure was logged rather than silently dropped.
    assert any("Login tracking write failed" in record.message for record in caplog.records)

    # The session survived it — a swallowed write that left the session needing a
    # rollback would break the NEXT thing every request did.
    assert db_session.query(User).count() == 1


def test_the_session_still_works_after_a_swallowed_failure(db_session):
    # Arrange — same failure, called directly, so the assertion is about the function's
    # contract rather than the route's.
    db_session.execute(text("DROP TABLE login_events"))
    db_session.commit()

    # Act — must not raise.
    record_successful_login(db_session, "some-user-id")

    # Assert — the session is usable, i.e. it was rolled back.
    assert db_session.query(User).count() == 0


# --- retention --------------------------------------------------------------------


def test_events_older_than_ninety_days_are_removed(db_session):
    # Arrange — one row either side of the boundary, plus one comfortably inside it.
    now = datetime.now(timezone.utc)
    ages = {
        "expired": now - timedelta(days=RETENTION_DAYS + 1),
        "just-inside": now - timedelta(days=RETENTION_DAYS - 1),
        "today": now,
    }
    for created_at in ages.values():
        db_session.add(LoginEvent(user_id="shared-demo-user", created_at=created_at))
    db_session.commit()
    assert db_session.query(LoginEvent).count() == 3

    # Act
    deleted = purge_expired_login_events(db_session)

    # Assert — the 91-day-old row is gone and the other two are not.
    assert deleted == 1
    remaining = {event.created_at for event in db_session.query(LoginEvent).all()}
    assert len(remaining) == 2
    cutoff = now - timedelta(days=RETENTION_DAYS)
    # Compared naive-to-naive: the column drops the offset on both backends.
    assert all(created_at > cutoff.replace(tzinfo=None) for created_at in remaining)


def test_a_purge_with_nothing_to_delete_deletes_nothing(client, account, db_session):
    # Arrange — a login that happened just now.
    assert login(client).status_code == 200

    # Act
    deleted = purge_expired_login_events(db_session)

    # Assert — the daily sweep runs against a table of fresh rows almost every time.
    assert deleted == 0
    assert db_session.query(LoginEvent).count() == 1


def test_retention_can_be_asked_about_a_different_now(db_session):
    """The sweep is time-driven, so `now` is injectable — otherwise this test would
    have to wait ninety days."""
    # Arrange — a row from today.
    db_session.add(LoginEvent(user_id="shared-demo-user"))
    db_session.commit()

    # Act — ask as if it were a hundred days from now.
    deleted = purge_expired_login_events(
        db_session, now=datetime.now(timezone.utc) + timedelta(days=100)
    )

    # Assert
    assert deleted == 1
    assert db_session.query(LoginEvent).count() == 0
