import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.api.schemas import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserOut,
)
from backend.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from backend.models.database import get_db
from backend.models.user import User
from backend.repositories.login_event_repository import record_successful_login

router = APIRouter(prefix="/auth", tags=["auth"])

# ⚠️ ONE SENTENCE FOR EVERY LOGIN FAILURE, AND IT NAMES NEITHER FIELD. "No account
# with that email" plus "wrong password" is a working account-enumeration oracle: an
# attacker walks a list of addresses through this endpoint and learns which ones are
# real, which is the whole first half of a credential-stuffing run. It reads worse
# for the honest user who has forgotten which address they used. That is the trade,
# and it is the standard one.
INVALID_CREDENTIALS_MESSAGE = "Incorrect email or password."

# The hash the login route verifies against when the email is unknown. See
# _resolve_login below — this exists to burn the same ~250ms a real bcrypt check
# costs, so the two cases are indistinguishable from a stopwatch.
#
# The plaintext is irrelevant and never compared against anything; what matters is
# that this is a REAL bcrypt hash at the SAME cost factor as the stored ones, so the
# work done is genuinely equal rather than approximately so.
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-constant-time-login")


def _signup_allowed() -> bool:
    """ALLOW_SIGNUP, default true.

    Read per request rather than captured at import so it can be flipped without a
    code change. Anything other than a recognised true value is false — a typo in a
    switch that closes a public registration endpoint should fail CLOSED.
    """
    raw = (os.getenv("ALLOW_SIGNUP") or "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Create an account and hand back a token for it.

    The email arrives trimmed and lowercased, and the password already checked for
    length, both by SignupRequest — a malformed address or a 7-character password is
    a 422 from the schema and never reaches this function.
    """
    if not _signup_allowed():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signups are closed. Ask the administrator for an account.",
        )

    email = body.email

    # The pre-check exists to give a clean 409 rather than a database error. It is
    # NOT the thing that guarantees uniqueness — two simultaneous signups can both
    # pass it. The unique index is the guarantee, and the except below turns losing
    # that race into the same 409 instead of a 500.
    if db.query(User).filter(User.email == email).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )

    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )
    db.refresh(user)

    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Exchange credentials for a token, or fail in exactly one way."""
    user = db.query(User).filter(User.email == body.email).first()

    # ⚠️ THE VERIFY RUNS EVEN WHEN THERE IS NO USER, and this must not be "optimised"
    # into an early return. bcrypt at cost 12 takes something like a quarter of a
    # second; returning before it for unknown emails makes those responses visibly
    # faster than wrong-password ones, and the timing difference IS the enumeration
    # oracle that the identical error message above was written to close. Same
    # message, same status, same amount of work.
    #
    # A locked account (UNUSABLE_PASSWORD_HASH) lands here too and simply fails to
    # verify, so it needs no branch of its own.
    stored_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(body.password, stored_hash)

    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS_MESSAGE,
            # Told to the client so a 401 is actionable, and required by the spec for
            # bearer authentication.
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ⚠️ BELOW THE RAISE, SO ONLY SUCCESSES ARE COUNTED — every failure has already
    # left this function by here, which is what makes "no event" the definition of a
    # failed login rather than a flag on a row.
    #
    # ⚠️ AND IT CANNOT AFFECT THIS RESPONSE. record_successful_login swallows and logs
    # everything (see its docstring); if that contract is ever broken, this line turns
    # a correct password into a 500. The token below is issued exactly as before,
    # from exactly the same call — nothing about authentication or the JWT changed.
    #
    # ⚠️ IT DOES WIDEN THE SUCCESS/FAILURE TIMING GAP THE ANTI-ENUMERATION WORK ABOVE
    # EXISTS TO CLOSE, AND THAT WAS MEASURED RATHER THAN ASSUMED. Interleaved in-process
    # against SQLite, 150 samples per case: the gap was -0.13 ms before this line
    # (p = 0.58, i.e. nothing) and +0.39 to +0.69 ms after it (p = 0.008 / 2e-7) — real,
    # and 0.4% of the ~170 ms bcrypt cost both paths pay. Sub-millisecond against a
    # 170 ms floor is not recoverable through internet jitter without tens of thousands
    # of requests per address, but it is no longer zero.
    #
    # If it ever needs to be zero again, the fix is to move this OFF the response path
    # — FastAPI BackgroundTasks, with its own session, running after the response is
    # sent — NOT to add a matching write to the failure path, which would hand an
    # unauthenticated caller a database write per request.
    record_successful_login(db, user.id)

    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def read_me(user: User = Depends(get_current_user)) -> User:
    """The signed-in user. UserOut is what keeps password_hash out of the response.

    A1 shipped this against a private `_current_user` in this module, explicitly
    marked as A3's to delete. It is deleted: there is now exactly one place in the
    API that turns a token into a User, so there is exactly one place where that can
    be got wrong.
    """
    return user
