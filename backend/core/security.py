"""Password hashing and JWT issuance. The only module that touches either.

⚠️ WHY THERE IS NO PASSLIB HERE, despite it being the usual answer and the one the
brief asked for. passlib's last release is 1.7.4, October 2020. bcrypt 5.0 made the
72-byte password limit raise instead of silently truncating, and passlib's backend
probe feeds it a longer-than-72-byte test string, so under passlib 1.7.4 + bcrypt
5.x EVERY hash call dies:

    >>> CryptContext(schemes=["bcrypt"]).hash("shortpw123")
    ValueError: password cannot be longer than 72 bytes

on a ten-character password. (There is a second, cosmetic breakage on the way in:
passlib reads `bcrypt.__about__.__version__`, removed in bcrypt 4.1, and logs a
trapped AttributeError.) The alternatives were pinning bcrypt below 5 to keep a
library that has been unmaintained for six years, or calling bcrypt directly.
bcrypt IS what passlib was wrapping; the wrapper bought us a `CryptContext` we were
not using for anything.

What passlib would genuinely have given us is scheme migration — `needs_update()`
and transparent rehashing when the cost factor changes. If that day comes, the hook
is verify_password: bcrypt hashes carry their own cost in the string ($2b$12$...),
so a rehash-on-login can read it back without any extra storage.
"""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv

# ⚠️ CALLED HERE, not left to main.py. backend/main.py loads the .env AFTER importing
# its routers, so by the time it runs, this module has already read the environment
# and raised on a missing secret. load_dotenv is idempotent and does not override
# variables that are already set, so calling it twice is free and a real environment
# variable still wins over the file.
load_dotenv()

JWT_ALGORITHM = "HS256"

# bcrypt's own default is 12 at the time of writing; stated explicitly because the
# whole point of a cost factor is that it is a deliberate choice, and a default that
# drifts underneath us is the one thing we would not notice.
BCRYPT_ROUNDS = 12

# ⚠️ A HARD LIMIT OF THE ALGORITHM, not a policy we chose. bcrypt hashes at most 72
# BYTES and bcrypt 5.x raises rather than truncating. Bytes, not characters: 40
# accented characters are 80 bytes in UTF-8, so a password well under any sane
# character limit can still cross this line.
MAX_PASSWORD_BYTES = 72

# Below this, a secret is short enough to be worth attacking offline. HS256 is
# HMAC-SHA256, so anything at or above 32 bytes of real entropy is beyond reach; the
# check is a floor against "changeme" and friends, not a strength meter.
MIN_JWT_SECRET_LENGTH = 32


def _load_jwt_secret() -> str:
    """Read JWT_SECRET, or refuse to start.

    ⚠️ NO FALLBACK, NO DEFAULT, NO GENERATED-AT-STARTUP VALUE. This secret is the
    only thing standing between an attacker and a signed token for any user id they
    like — a known fallback is a master key published in the repository, and a
    per-process random one silently invalidates every session on restart and works
    fine in exactly the single-process dev setup where you would never notice.

    Raising at import is the point: the failure lands on whoever is starting the
    process, in the terminal, before a single request is served.
    """
    secret = (os.getenv("JWT_SECRET") or "").strip()
    if not secret:
        raise RuntimeError(
            "JWT_SECRET is not set. This is the signing key for every access token "
            "the app issues — treat it as a master key. Generate one with:\n"
            "    python -c \"import secrets; print(secrets.token_urlsafe(48))\"\n"
            "and add it to your .env as JWT_SECRET=..."
        )
    if len(secret) < MIN_JWT_SECRET_LENGTH:
        raise RuntimeError(
            f"JWT_SECRET is only {len(secret)} characters; at least "
            f"{MIN_JWT_SECRET_LENGTH} are required. A short signing key can be "
            "brute-forced offline from a single captured token, which yields a "
            "master key for every account. Generate one with:\n"
            "    python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    return secret


def _load_expiry_minutes() -> int:
    """ACCESS_TOKEN_EXPIRE_MINUTES, defaulting to 24 hours.

    A malformed value raises rather than falling back: silently reverting to the
    default would turn a typo into tokens that live far longer than intended, which
    is not a thing anyone would go looking for.
    """
    raw = (os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES") or "").strip()
    if not raw:
        return 1440
    try:
        minutes = int(raw)
    except ValueError as cause:
        raise RuntimeError(
            f"ACCESS_TOKEN_EXPIRE_MINUTES must be a whole number of minutes, got {raw!r}"
        ) from cause
    if minutes <= 0:
        raise RuntimeError(
            f"ACCESS_TOKEN_EXPIRE_MINUTES must be positive, got {minutes}"
        )
    return minutes


JWT_SECRET = _load_jwt_secret()
ACCESS_TOKEN_EXPIRE_MINUTES = _load_expiry_minutes()


# --- passwords --------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """bcrypt at cost 12. The salt is generated per call and stored in the result."""
    encoded = plain.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        # Raised rather than truncated. Truncating silently means "correcthorse..."
        # and "correcthorse...<anything>" become the same password, so a user who
        # sets a 100-byte passphrase has a shorter one than they think and no way to
        # find out. Callers validate this before they get here; this is the backstop.
        raise ValueError(
            f"Password is {len(encoded)} bytes; bcrypt accepts at most "
            f"{MAX_PASSWORD_BYTES}."
        )
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """True only for the right password against a real hash. Never raises.

    ⚠️ EVERY FAILURE MODE COLLAPSES TO False, deliberately. `hashed` can be the
    UNUSABLE_PASSWORD_HASH marker of a locked account, or a corrupt row, or the dummy
    hash the login route verifies against for unknown emails — bcrypt raises on all
    of them. An exception escaping here would be a 500 that distinguishes those cases
    from a merely wrong password, which is precisely the signal login must not leak.
    """
    encoded = plain.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        # Cannot match any stored hash — nothing over 72 bytes was ever hashable.
        return False
    try:
        return bcrypt.checkpw(encoded, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- tokens -----------------------------------------------------------------------


def create_access_token(user_id: str) -> str:
    """A signed JWT carrying the user id as `sub`, expiring per configuration."""
    now = datetime.now(timezone.utc)
    payload = {
        # A string, always: `sub` is a registered claim that some validators reject
        # when it is not one, and PyJWT is moving toward enforcing that too.
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """The user id from a valid token, or None. Never raises on bad input.

    ⚠️ `algorithms` IS PINNED TO A LITERAL LIST and must stay that way. Letting the
    token's own header choose the algorithm is the classic JWT forgery: an attacker
    re-signs with `alg: none`, or with HS256 against a public key the server thought
    it was using for RS256, and the library obligingly agrees.

    None covers expired, tampered, wrongly-signed, structurally invalid, and
    missing-`sub` alike. The caller gets one answer — "no user" — because there is
    nothing it could usefully do differently, and an endpoint that reported WHY a
    token failed would be telling an attacker how close they are.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        # The base class of the whole PyJWT hierarchy: ExpiredSignatureError,
        # InvalidSignatureError, DecodeError and the rest all inherit from it.
        return None
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        return None
    return subject
