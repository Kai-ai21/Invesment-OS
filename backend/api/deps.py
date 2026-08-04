"""Who the request is, enforced. Every route but three depends on this.

A2 made the repositories require a user_id; A3 makes the API require a real token to
get one. The fallback-to-demo dependency A2 shipped with (backend/api/dependencies.py)
is deleted, not disabled — a switch that turns authentication off is a switch someone
eventually flips.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.core.security import decode_access_token
from backend.models.database import get_db
from backend.models.user import User

# ⚠️ auto_error=False IS WHAT MAKES THE STATUS CODE OURS, and that is the part worth
# guarding. Every rejection in this module goes through the one function below, so a
# missing header, a malformed one, an expired token and a forged token cannot drift
# apart into distinguishable answers — see _unauthenticated.
#
# On the scheme itself: OAuth2PasswordBearer is what FastAPI's own docs use for a
# bearer-token flow, and HTTPBearer historically answered a MISSING header with 403,
# which is precisely the 401/403 confusion this stage exists to avoid. That is fixed
# in the version pinned here — measured, not assumed: on fastapi 0.139.2 both schemes
# return 401 for a missing header. So the choice is convention rather than necessity,
# and with auto_error=False neither scheme's default is reached anyway.
#
# `tokenUrl` is metadata for the OpenAPI docs' Authorize button and changes no
# behaviour. It points at /auth/login, which takes JSON rather than the OAuth2 form
# body, so Swagger's built-in Authorize flow will not work against it — post to
# /auth/login yourself and paste the token. Noted rather than "fixed" by reshaping a
# working endpoint around a docs affordance.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def _unauthenticated() -> HTTPException:
    """⚠️ ONE ERROR FOR EVERY AUTHENTICATION FAILURE.

    Missing header, wrong scheme, expired token, tampered token, token for a user who
    has since been deleted — all 401, all the same sentence. Distinguishing them
    would be a small kindness to a confused user and a large one to an attacker:
    "expired" versus "invalid signature" tells them their forgery is structurally
    right, and a distinct answer for a deleted user confirms that the id in the token
    was once real.

    WWW-Authenticate is not decoration. RFC 9110 requires it on a 401, and it is what
    tells a client which scheme to retry with.
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """The signed-in user, or 401. Never returns None, never returns 403."""
    if token is None:
        # Covers both no Authorization header at all and one whose scheme is not
        # Bearer — OAuth2PasswordBearer hands back None for each.
        raise _unauthenticated()

    user_id = decode_access_token(token)
    if user_id is None:
        # Signature, expiry, structure and a missing `sub` all land here; see
        # core/security.decode_access_token, which deliberately reports no detail.
        raise _unauthenticated()

    # ⚠️ THE DATABASE DECIDES, NOT THE CLAIM. A valid signature only proves WE issued
    # the token, not that the account still exists. Tokens live 24 hours by default,
    # so a deleted user's token stays cryptographically perfect for up to a day after
    # the row is gone — and every downstream repository call would then scope to a
    # user_id that owns nothing, which fails quietly rather than loudly.
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise _unauthenticated()

    return user


def get_current_user_id(user: User = Depends(get_current_user)) -> str:
    """Sugar for the routes that only need the id. Same chain, same 401s."""
    return user.id
