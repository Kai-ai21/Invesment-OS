"""A3: every route requires a valid token, except the three that cannot.

⚠️ THE REGISTRY TEST AT THE BOTTOM IS THE ONE THAT MATTERS LONG-TERM. Protection is
opt-IN: a route added without the dependency is public and looks completely normal in
the diff — no error, no warning, nothing to notice in review. That test walks the
dependency tree FastAPI actually executes and fails on any route that is neither
protected nor explicitly listed as public, so the next endpoint someone adds cannot
be quietly world-readable.
"""

import warnings
from datetime import datetime, timedelta, timezone

import pytest

warnings.filterwarnings("ignore")

import jwt  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.api.deps import get_current_user  # noqa: E402
from backend.core.security import (  # noqa: E402
    JWT_ALGORITHM,
    JWT_SECRET,
    create_access_token,
    hash_password,
)
from backend.main import app  # noqa: E402
from backend.models.base import Base  # noqa: E402
from backend.models.claim import Claim  # noqa: E402 — Thesis.claims needs the mapper
from backend.models.database import get_db  # noqa: E402
from backend.models.thesis import Thesis  # noqa: E402 (registers mapper)
from backend.models.user import User  # noqa: E402

# ⚠️ THE ONLY ROUTES ALLOWED TO BE PUBLIC, and each one has to be.
#
#   GET  /health       — the liveness probe. Whatever watches this process has no
#                        credentials and must not need any; requiring a token would
#                        mean an outage in auth reads as the whole service being up,
#                        or the monitor holding a permanent one. It returns a
#                        constant and touches no database.
#   POST /auth/signup  — creates the account. Nothing to authenticate as yet. Gated
#                        separately by ALLOW_SIGNUP (A1), which is the control that
#                        actually closes registration.
#   POST /auth/login   — exchanges credentials for the token. Requiring a token to
#                        get a token is the obvious circularity.
PUBLIC_ROUTES = {
    ("GET", "/health"),
    ("POST", "/auth/signup"),
    ("POST", "/auth/login"),
}


def all_routes():
    """Every APIRoute, walking included routers.

    This FastAPI version wraps `include_router` results in a private `_IncludedRouter`
    rather than flattening them into `app.routes`, so a naive pass over `app.routes`
    sees ONE route (/health) and would let this whole file pass while testing nothing.
    """

    def walk(routes):
        for route in routes:
            if isinstance(route, APIRoute):
                yield route
            elif hasattr(route, "original_router"):
                yield from walk(route.original_router.routes)

    return list(walk(app.routes))


def is_protected(route) -> bool:
    """Whether get_current_user is in the dependency tree FastAPI will execute.

    Resolved from the dependant graph rather than by reading the signature, so a
    parameter merely NAMED `user`, or one wired to some other dependency, does not
    count as protection.
    """
    seen, stack = set(), [route.dependant]
    while stack:
        dependant = stack.pop()
        if id(dependant) in seen:
            continue
        seen.add(id(dependant))
        if dependant.call is get_current_user:
            return True
        stack.extend(dependant.dependencies)
    return False


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
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def user(db_session):
    row = User(email="ada@example.com", password_hash=hash_password("a-real-password"))
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


# A protected route that needs no path parameters and no request body, so these tests
# exercise authentication rather than validation.
PROBE = "/theses"


def assert_unauthenticated(response):
    """401 with the WWW-Authenticate challenge — and specifically NOT 403.

    ⚠️ 401 MEANS "WE DO NOT KNOW WHO YOU ARE"; 403 MEANS "WE KNOW, AND NO". Getting
    this backwards tells an anonymous caller that the resource exists and that their
    identity was understood, and it sends clients down a "you lack permission" path
    when what they actually need is to log in. FastAPI's HTTPBearer returns 403 for a
    missing header, which is why deps.py uses OAuth2PasswordBearer.
    """
    assert response.status_code == 401, (
        f"expected 401, got {response.status_code}: {response.text[:200]}"
    )
    assert response.headers.get("WWW-Authenticate") == "Bearer"


# --- the six failure modes --------------------------------------------------------


def test_no_authorization_header_is_401(client):
    assert_unauthenticated(client.get(PROBE))


@pytest.mark.parametrize(
    "header",
    [
        "",                       # present but empty
        "nonsense",               # no scheme
        "Bearer",                 # scheme with no token
        "Bearer ",                # scheme with an empty token
        "Basic abc123",           # the wrong scheme entirely
        "bearer",                 # scheme alone, lowercased
        "Token abc123",           # a plausible-looking wrong scheme
    ],
)
def test_malformed_authorization_header_is_401(client, header):
    assert_unauthenticated(client.get(PROBE, headers={"Authorization": header}))


def test_expired_token_is_401(client, user):
    # Arrange — signed by us, correctly, but past its exp.
    expired = jwt.encode(
        {"sub": user.id, "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    # Act / Assert
    assert_unauthenticated(client.get(PROBE, headers={"Authorization": f"Bearer {expired}"}))


def test_tampered_token_is_401(client, user):
    # Arrange — flip one character of the payload; the signature no longer matches.
    token = create_access_token(user.id)
    header, payload, signature = token.split(".")
    swapped = "B" if payload[5] != "B" else "C"
    tampered = f"{header}.{payload[:5]}{swapped}{payload[6:]}.{signature}"
    assert tampered != token

    # Act / Assert
    assert_unauthenticated(client.get(PROBE, headers={"Authorization": f"Bearer {tampered}"}))


def test_token_signed_with_another_secret_is_401(client, user):
    forged = jwt.encode(
        {"sub": user.id, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "an-attackers-own-secret-of-sufficient-length",
        algorithm=JWT_ALGORITHM,
    )
    assert_unauthenticated(client.get(PROBE, headers={"Authorization": f"Bearer {forged}"}))


def test_token_for_a_deleted_user_is_401(client, db_session, user):
    """⚠️ THE SIGNATURE IS STILL PERFECTLY VALID HERE.

    A token stays cryptographically correct for its full 24-hour life, so the row has
    to be looked up rather than trusted from the `sub` claim. Without that check this
    request would sail through and every repository call downstream would scope to a
    user id that owns nothing — succeeding, quietly, with empty results.
    """
    # Arrange
    token = create_access_token(user.id)
    assert client.get(PROBE, headers={"Authorization": f"Bearer {token}"}).status_code == 200

    db_session.delete(user)
    db_session.commit()

    # Act / Assert
    assert_unauthenticated(client.get(PROBE, headers={"Authorization": f"Bearer {token}"}))


def test_valid_token_is_200(client, user):
    response = client.get(PROBE, headers={"Authorization": f"Bearer {create_access_token(user.id)}"})
    assert response.status_code == 200
    assert response.json() == []


def test_every_failure_mode_answers_identically(client, user):
    """One response for all of them, so nothing distinguishes the causes.

    "Expired" versus "bad signature" tells a forger their token is structurally right
    and only stale; a distinct answer for a deleted user confirms the id was once
    real. There is nothing a legitimate client would do differently, either — all of
    these mean "log in again".
    """
    expired = jwt.encode(
        {"sub": user.id, "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    forged = jwt.encode(
        {"sub": user.id, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "an-attackers-own-secret-of-sufficient-length",
        algorithm=JWT_ALGORITHM,
    )
    unknown_user = create_access_token("00000000-0000-0000-0000-000000000000")

    answers = {
        (r.status_code, r.text)
        for r in [
            client.get(PROBE),
            client.get(PROBE, headers={"Authorization": "nonsense"}),
            client.get(PROBE, headers={"Authorization": f"Bearer {expired}"}),
            client.get(PROBE, headers={"Authorization": f"Bearer {forged}"}),
            client.get(PROBE, headers={"Authorization": f"Bearer {unknown_user}"}),
        ]
    }
    assert len(answers) == 1, f"auth failures are distinguishable: {answers}"


# --- the public three -------------------------------------------------------------


def test_health_works_with_no_token(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_signup_works_with_no_token(client, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    response = client.post(
        "/auth/signup", json={"email": "new@example.com", "password": "a-real-password"}
    )
    assert response.status_code == 201
    assert "access_token" in response.json()


def test_login_works_with_no_token(client, user):
    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "a-real-password"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_auth_me_uses_the_shared_dependency(client, user):
    """D: the temporary inline check in A1 is gone."""
    import backend.api.auth as auth_module

    assert not hasattr(auth_module, "_current_user"), (
        "the A1 placeholder is still present; /auth/me must use deps.get_current_user"
    )

    assert_unauthenticated(client.get("/auth/me"))
    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {create_access_token(user.id)}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"
    assert "password_hash" not in response.json()


# --- the registry -----------------------------------------------------------------


def test_the_route_walker_actually_finds_the_routes():
    """Guards the guard.

    If `all_routes` silently returned one route — which a naive walk of `app.routes`
    does on this FastAPI version — every assertion below would pass while checking
    almost nothing. This pins the count to something that cannot be a walking bug.
    """
    routes = all_routes()
    assert len(routes) > 30, f"route walking is broken: found only {len(routes)}"
    paths = {r.path for r in routes}
    for expected in ["/theses", "/holdings", "/alerts", "/auth/me", "/health"]:
        assert expected in paths


def test_every_route_is_protected_or_explicitly_public():
    """⚠️ THE ONE THAT CATCHES THE NEXT UNPROTECTED ENDPOINT.

    This found three during A3 itself — GET /filings/{ticker}, GET /news/{ticker} and
    POST /theses/enhance-reasoning, the last of which spends an AI call on
    caller-supplied text. All three had been missed by hand and all three looked
    entirely normal in the source.
    """
    unprotected = {
        (sorted(route.methods)[0], route.path)
        for route in all_routes()
        if not is_protected(route)
    }
    assert unprotected == PUBLIC_ROUTES, (
        f"unexpectedly public: {sorted(unprotected - PUBLIC_ROUTES)}; "
        f"unexpectedly protected: {sorted(PUBLIC_ROUTES - unprotected)}"
    )


def test_every_protected_route_actually_rejects_an_anonymous_request():
    """The dependency tree says protected; this proves the wire agrees.

    Every protected route is called with NO token and must answer 401 — not 404, not
    422, not 500. A route that 422s on a missing body before checking the token would
    be leaking the fact that it exists and is willing to talk.
    """
    client = TestClient(app)
    failures = []
    for route in all_routes():
        method = sorted(route.methods)[0]
        if (method, route.path) in PUBLIC_ROUTES:
            continue
        # Any placeholder works — auth must be refused before the id is ever looked at.
        path = route.path
        for name in route.param_convertors:
            path = path.replace(f"{{{name}}}", "probe")
        response = client.request(method, path, json={})
        if response.status_code != 401:
            failures.append(f"{method} {path} -> {response.status_code}")
    assert not failures, "protected routes not answering 401 anonymously: " + str(failures)
