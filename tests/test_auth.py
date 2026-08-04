"""Auth A1: hashing, token issuance, and the two things login must never leak."""

import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.security import (
    JWT_ALGORITHM,
    JWT_SECRET,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from backend.main import app
from backend.models.base import Base
from backend.models.claim import Claim  # noqa: F401 — Thesis.claims cannot resolve without it
from backend.models.database import get_db
from backend.models.thesis import Thesis  # noqa: F401 (registers mapper with Base)
from backend.models.user import UNUSABLE_PASSWORD_HASH, User

PASSWORD = "correct-horse-battery"


@pytest.fixture
def db_session():
    """A private in-memory database per test.

    StaticPool with a shared connection so the request handler and the assertions in
    the test body see the same database — a fresh connection to :memory: would be a
    different, empty one.
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


def signup(client, email=" Ada@Example.com ", password=PASSWORD):
    return client.post("/auth/signup", json={"email": email, "password": password})


# --- signup -----------------------------------------------------------------------


def test_signup_stores_a_hash_and_never_the_plaintext(client, db_session):
    # Act
    response = signup(client)

    # Assert — the token is the visible half; the stored row is the half that matters.
    assert response.status_code == 201
    stored = db_session.query(User).one()

    # The plaintext must not appear ANYWHERE on the row, under any column. Comparing
    # only against password_hash would pass if someone later added a `password`
    # column beside it.
    row = {column.name: getattr(stored, column.name) for column in User.__table__.columns}
    assert PASSWORD not in row.values()
    assert not any(PASSWORD in str(value) for value in row.values())

    # It is a real bcrypt hash at the configured cost, and it verifies.
    assert stored.password_hash.startswith("$2b$12$")
    assert verify_password(PASSWORD, stored.password_hash)
    assert not verify_password("not-the-password", stored.password_hash)


def test_signup_normalises_the_email(client, db_session):
    # Act — mixed case and surrounding whitespace.
    signup(client, email="  Ada@Example.COM  ")

    # Assert — stored trimmed and lowercased, so the unique index actually bites.
    assert db_session.query(User).one().email == "ada@example.com"


def test_signup_with_an_existing_email_is_409(client):
    # Arrange
    assert signup(client).status_code == 201

    # Act — same address, differently typed, to prove the check runs on the
    # normalised form rather than the raw string.
    response = signup(client, email="ADA@example.com", password="a-different-one")

    # Assert
    assert response.status_code == 409


def test_signup_rejects_a_password_under_eight_characters(client, db_session):
    # Act
    response = signup(client, password="short7!")

    # Assert — 422 from the schema, and nothing written.
    assert response.status_code == 422
    assert db_session.query(User).count() == 0


def test_signup_rejects_a_password_over_bcrypts_72_byte_limit(client, db_session):
    # Arrange — 40 accented characters: comfortably under any character limit, but 80
    # bytes in UTF-8. bcrypt 5.x RAISES above 72 bytes rather than truncating, so
    # without the byte-level check this is a 500 rather than a validation error.
    password = "é" * 40
    assert len(password) == 40 and len(password.encode("utf-8")) == 80

    # Act
    response = client.post(
        "/auth/signup", json={"email": "ada@example.com", "password": password}
    )

    # Assert
    assert response.status_code == 422
    assert db_session.query(User).count() == 0


def test_signup_is_blocked_when_allow_signup_is_false(client, db_session, monkeypatch):
    # Arrange
    monkeypatch.setenv("ALLOW_SIGNUP", "false")

    # Act
    response = signup(client)

    # Assert — 403, and no account created.
    assert response.status_code == 403
    assert db_session.query(User).count() == 0


def test_allow_signup_fails_closed_on_an_unrecognised_value(client, monkeypatch):
    # Arrange — a typo in the switch. Fail CLOSED: an unreadable value must not
    # reopen public registration.
    monkeypatch.setenv("ALLOW_SIGNUP", "flase")

    # Act / Assert
    assert signup(client).status_code == 403


# --- login ------------------------------------------------------------------------


def test_login_with_correct_credentials_returns_a_token(client, db_session):
    # Arrange
    signup(client)
    user_id = db_session.query(User).one().id

    # Act
    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": PASSWORD}
    )

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert decode_access_token(body["access_token"]) == user_id


def test_wrong_password_and_unknown_email_are_indistinguishable(client):
    """⚠️ THE ANTI-ENUMERATION TEST. If this fails, the endpoint is an oracle for
    which email addresses have accounts."""
    # Arrange
    signup(client)

    # Act
    wrong_password = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "wrong-password"}
    )
    unknown_email = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )

    # Assert — same status, same body, byte for byte.
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["detail"] == "Incorrect email or password."


def test_login_hashes_even_when_the_email_is_unknown(client, monkeypatch):
    """The timing half of the same defence.

    Wall-clock timing is far too flaky to assert on in a test suite, so this asserts
    the BEHAVIOUR that produces constant time instead: that a login for an address
    with no account still performs a bcrypt verification. An early return for unknown
    emails would leave this counter at zero.
    """
    # Arrange
    import backend.api.auth as auth_module

    calls = []
    real_verify = auth_module.verify_password
    monkeypatch.setattr(
        auth_module,
        "verify_password",
        lambda plain, hashed: calls.append(hashed) or real_verify(plain, hashed),
    )

    # Act
    response = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )

    # Assert — it verified, against the dummy hash, and still refused.
    assert response.status_code == 401
    assert len(calls) == 1
    assert calls[0].startswith("$2b$12$")


def test_a_locked_legacy_account_cannot_be_logged_into(client, db_session):
    """demo@local owns all the pre-auth data and is seeded with an unusable hash."""
    # Arrange
    db_session.add(User(email="demo@local", password_hash=UNUSABLE_PASSWORD_HASH))
    db_session.commit()

    # Act — try the marker itself as the password, and the empty string.
    for attempt in [UNUSABLE_PASSWORD_HASH, "", "password"]:
        response = client.post(
            "/auth/login", json={"email": "demo@local", "password": attempt}
        )

        # Assert — refused, with the ordinary message and no 500.
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect email or password."


# --- tokens -----------------------------------------------------------------------


def test_a_token_decodes_back_to_the_right_user_id():
    # Act
    token = create_access_token("user-abc-123")

    # Assert
    assert decode_access_token(token) == "user-abc-123"


def test_an_expired_token_decodes_to_none():
    # Arrange — signed by us, correctly, but already past its exp.
    expired = jwt.encode(
        {
            "sub": "user-abc-123",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    # Act / Assert
    assert decode_access_token(expired) is None


def test_a_tampered_token_decodes_to_none():
    # Arrange — flip one character of the payload segment. The signature no longer
    # matches, which is the entire security property of a JWT.
    token = create_access_token("user-abc-123")
    header, payload, signature = token.split(".")
    swapped = "B" if payload[5] != "B" else "C"
    tampered = f"{header}.{payload[:5]}{swapped}{payload[6:]}.{signature}"
    assert tampered != token

    # Act / Assert
    assert decode_access_token(tampered) is None


def test_a_token_signed_with_another_secret_decodes_to_none():
    # Arrange — the forgery this is all guarding against.
    forged = jwt.encode(
        {"sub": "user-abc-123", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "an-attackers-own-secret-of-sufficient-length",
        algorithm=JWT_ALGORITHM,
    )

    # Act / Assert
    assert decode_access_token(forged) is None


def test_structurally_invalid_tokens_decode_to_none():
    # Act / Assert — none of these may raise.
    for rubbish in ["", "not-a-token", "a.b.c", "...", "Bearer " + create_access_token("x")]:
        assert decode_access_token(rubbish) is None


# --- /auth/me ---------------------------------------------------------------------


def test_me_returns_the_current_user_without_the_hash(client, db_session):
    # Arrange
    token = signup(client).json()["access_token"]

    # Act
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert body["id"] == db_session.query(User).one().id
    # ⚠️ The response must not carry the hash under any key.
    assert "password_hash" not in body
    assert not any("$2b$" in str(value) for value in body.values())


def test_me_rejects_a_missing_or_bad_token(client):
    # Act / Assert
    assert client.get("/auth/me").status_code == 401
    assert (
        client.get("/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code
        == 401
    )


# --- startup guards ---------------------------------------------------------------
#
# Run in a SUBPROCESS because the thing under test happens at import: the module is
# already imported in this process, so reimporting it here would prove nothing.


def _import_security_with(secret: str | None) -> subprocess.CompletedProcess:
    script = textwrap.dedent(
        """
        import os, sys
        os.environ.pop("JWT_SECRET", None)
        secret = sys.argv[1] if len(sys.argv) > 1 else None
        if secret is not None:
            os.environ["JWT_SECRET"] = secret
        # Neutralise any .env on disk, which load_dotenv would otherwise supply.
        import dotenv
        dotenv.load_dotenv = lambda *a, **k: False
        import backend.core.security
        print("IMPORTED")
        """
    )
    return subprocess.run(
        [sys.executable, "-c", script] + ([secret] if secret is not None else []),
        capture_output=True,
        text=True,
    )


def test_import_fails_loudly_when_the_jwt_secret_is_missing():
    # Act
    result = _import_security_with(None)

    # Assert — no import, and the message says what to do about it.
    assert result.returncode != 0
    assert "IMPORTED" not in result.stdout
    assert "JWT_SECRET is not set" in result.stderr


def test_import_fails_loudly_when_the_jwt_secret_is_too_short():
    # Act — 31 characters, one under the floor.
    result = _import_security_with("x" * 31)

    # Assert
    assert result.returncode != 0
    assert "IMPORTED" not in result.stdout
    assert "at least 32" in result.stderr


def test_import_succeeds_with_a_long_secret():
    # Act
    result = _import_security_with("x" * 32)

    # Assert — the guard is a floor, not a blanket refusal.
    assert result.returncode == 0, result.stderr
    assert "IMPORTED" in result.stdout


# --- hashing ----------------------------------------------------------------------


def test_the_same_password_hashes_differently_every_time():
    # Act — per-hash salt, so two users with the same password are not visibly
    # matched to each other in a stolen database.
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)

    # Assert
    assert first != second
    assert verify_password(PASSWORD, first)
    assert verify_password(PASSWORD, second)


def test_verify_password_never_raises_on_a_malformed_hash():
    # Act / Assert — an exception here would be a 500 that distinguishes a corrupt or
    # locked row from a merely wrong password.
    for bad in [UNUSABLE_PASSWORD_HASH, "", "not-a-hash", "$2b$12$too-short"]:
        assert verify_password(PASSWORD, bad) is False
