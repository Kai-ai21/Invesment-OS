"""Who the request is acting as. Every user-scoped endpoint depends on this.

⚠️ THIS MODULE IS THE ONLY PLACE A user_id ENTERS THE API. Repository functions all
require one (see A2), so the single question an endpoint has to answer is "whose data
is this", and it answers it by depending on `current_user_id` rather than by reaching
for the demo user itself.
"""

import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.core.security import decode_access_token
from backend.models.database import get_db
from backend.models.user import User

# auto_error=False so a request with NO Authorization header reaches the function
# below rather than being rejected by the scheme. That is what makes the fallback
# possible; when the fallback goes, this becomes auto_error=True.
_bearer_scheme = HTTPBearer(auto_error=False)

DEMO_EMAIL = "demo@local"


def _fallback_to_demo_user() -> bool:
    """Whether an UNAUTHENTICATED request is served as demo@local.

    ⚠️ THIS IS A3's KILL SWITCH AND IT IS TEMPORARY. Until the frontend has a login
    screen, nothing sends an Authorization header, so refusing anonymous requests here
    would take the whole app offline mid-migration. The fallback keeps single-user
    behaviour exactly as it was WHILE the scoping underneath becomes real: a request
    that DOES carry a token is scoped to that token's user, always.

    It is deliberately not a security boundary and must not be mistaken for one — an
    anonymous caller gets demo@local's data, which is precisely what an anonymous
    caller already got before A2. What A2 buys is that user B, signed in, can no
    longer reach user A's rows. A3 sets AUTH_REQUIRED=true and deletes this function.
    """
    raw = (os.getenv("AUTH_REQUIRED") or "false").strip().lower()
    return raw not in {"1", "true", "yes", "on"}


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """The signed-in user, or demo@local while the fallback stands."""
    if credentials is not None:
        user_id = decode_access_token(credentials.credentials)
        if user_id is None:
            # ⚠️ A BAD TOKEN IS ALWAYS A 401, NEVER A FALLBACK. Quietly serving
            # demo@local's data to someone whose expired token just failed would be
            # the worst of both worlds: they would see somebody else's portfolio and
            # have no idea they were not signed in.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # The database decides, not the claim — see the same note in api/auth.py.
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    if not _fallback_to_demo_user():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    demo = db.query(User).filter(User.email == DEMO_EMAIL).first()
    if demo is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return demo


def current_user_id(user: User = Depends(current_user)) -> str:
    """Just the id, which is all most endpoints need to pass to a repository."""
    return user.id
