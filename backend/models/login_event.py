import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class LoginEvent(Base):
    """One row per SUCCESSFUL login. Three columns, and there is not a fourth.

    WHY IT EXISTS. The demo account is shared with a few dozen people, and the only
    question being asked of this table is "how many times has anyone signed in, and
    when". Nothing here identifies WHO signed in — see the note on user_id.

    ⚠️ WHAT IS DELIBERATELY ABSENT, so that adding any of it is a decision someone has
    to make on purpose rather than a field they slipped in: no IP address, no user
    agent, no session or token id, no email, no password material, no country, no
    device. A row is a timestamp and an account, and that is the whole design — the
    README tells shared-account users exactly this, so a new column here would make
    that statement false. tests/test_login_tracking.py asserts the column set.

    ⚠️ FAILURES ARE NOT RECORDED, and that is not an oversight either. A failed-login
    table is a far more sensitive object (it accumulates the addresses people typed,
    which includes the ones they mistyped from other services), and counting failures
    was not the question. See backend/api/auth.py: the write happens only after the
    credentials check has already passed.
    """

    __tablename__ = "login_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # ⚠️ ON A SHARED ACCOUNT THIS COLUMN IS A CONSTANT. Fifty people logging into one
    # demo account produce fifty rows with the same user_id, so it separates accounts
    # and never people. It is here because the table would be meaningless the moment a
    # second account exists, not because it tells you anything about the demo.
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )

    # Indexed because the ONLY two queries are "order by time" and "delete everything
    # older than the cutoff" (see login_event_repository.purge_expired_login_events),
    # and the second one scans the whole table without it.
    #
    # Naive-UTC on the way in and on the way out, matching every other timestamp in
    # this codebase (Alert.created_at, Pattern.generated_at): the column is a plain
    # DateTime, and both SQLite and Postgres drop the offset from the aware value this
    # default produces. Consistent on both sides, so comparisons against a UTC cutoff
    # are correct — which is what the 90-day retention test actually proves.
    created_at: Mapped[datetime] = mapped_column(
        DateTime, index=True, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
