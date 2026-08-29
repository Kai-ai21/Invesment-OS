"""Writes and expires login events. The only module that touches the table.

Two functions with deliberately OPPOSITE error contracts, and the difference is the
point:

  - record_successful_login NEVER RAISES. It sits on the authentication path, and
    analytics must not be able to lock anyone out.
  - purge_expired_login_events RAISES. It runs from a retention sweep and from a
    script, where a silent failure means data quietly kept past its retention — the
    one failure nobody would notice.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.models.login_event import LoginEvent

logger = logging.getLogger(__name__)

# How long an event is kept. Stated once, here: the retention sweep, the script and
# the README note all read this rather than repeating "90" in four places, because a
# retention period documented in one place and enforced in another drifts.
RETENTION_DAYS = 90


def record_successful_login(db: Session, user_id: str) -> None:
    """Record one successful login. NEVER RAISES, EVER, FOR ANY REASON.

    ⚠️ THIS IS THE WHOLE SAFETY PROPERTY OF THE FEATURE. It is called from the login
    route, so anything that escapes it becomes a 500 on the way to a token that had
    already been earned — the user typed the right password and gets locked out
    because a counter failed. The blanket `except Exception` is not laziness about
    which errors are expected; it is the requirement. Missing table, dead connection,
    disk full, a pooled connection the pooler closed underneath us: all of them are
    "this login went uncounted", none of them are "this login failed".

    The rollback matters as much as the swallow. A failed flush leaves the session in
    a state where every later statement on it raises PendingRollbackError, so without
    it a swallowed write would still poison whatever the request did next.

    ⚠️ NOTHING ABOUT THE FAILURE IS WRITTEN TO THE DATABASE, and the log line carries
    no user id or email either. The README promises that a timestamp and an account id
    are all that is kept; a diagnostic path that quietly logged more would make that
    promise false in exactly the place nobody thinks to look. The traceback says which
    query broke, which is what an operator actually needs.
    """
    try:
        db.add(LoginEvent(user_id=user_id))
        db.commit()
    except Exception:
        logger.warning(
            "Login tracking write failed; the login itself is unaffected.",
            exc_info=True,
        )
        try:
            db.rollback()
        except Exception:
            # The session is beyond saving. It is closed by get_db's finally block
            # regardless, and re-raising here would defeat the entire point of the
            # function.
            logger.warning("Rollback after a failed login-tracking write also failed.", exc_info=True)


def purge_expired_login_events(db: Session, *, now: datetime | None = None) -> int:
    """Delete events older than RETENTION_DAYS. Returns how many were deleted.

    `now` is injectable so the retention test can assert on a real 91-day-old row
    rather than sleeping for three months.

    synchronize_session=False because nothing in this process holds LoginEvent objects
    in memory to keep consistent — this is a bulk DELETE on rows no one is looking at,
    and the default strategy would fetch every matching row first just to expire it.
    """
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=RETENTION_DAYS)
    deleted = (
        db.query(LoginEvent)
        .filter(LoginEvent.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted
