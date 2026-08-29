#!/usr/bin/env python
"""How many times has anyone successfully logged in, and when.

⚠️ THERE IS NO ENDPOINT FOR THIS AND THERE SHOULD NOT BE. Login counts are operator
data, not product data: an API route would have to be authorised, and the only account
that would plausibly hold that authorisation on this deployment is the shared demo one
— which is the account being counted. A local script against DATABASE_URL needs the
database password to run, which is exactly the right bar.

USAGE
    python -m scripts.login_activity                 # everything still retained
    python -m scripts.login_activity --days 30       # last 30 days only
    python -m scripts.login_activity --prune         # run the 90-day deletion now

WHICH DATABASE IT READS. The same one the app would open: DATABASE_URL from the
environment, or from .env, and the local SQLite file when neither sets it. To point it
at production from your laptop, put the URL in front of the command rather than in
.env — a real environment variable wins over the file, and nothing is left on disk:

    DATABASE_URL='postgresql://…' python -m scripts.login_activity

JWT_SECRET is NOT needed. This script never imports backend.core.security, so it runs
against a database with nothing but the connection string.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from sqlalchemy import inspect

# ⚠️ BEFORE THE backend.models IMPORT BELOW, which is why it is not with the rest.
# backend/models/database.py reads DATABASE_URL AT IMPORT to build the engine, so a
# load_dotenv() that ran afterwards would silently leave this script talking to the
# local SQLite file while reporting on "the database".
load_dotenv()

from backend.models.database import DATABASE_URL, SessionLocal, engine  # noqa: E402
from backend.models.login_event import LoginEvent  # noqa: E402
from backend.models.user import User  # noqa: E402
from backend.repositories.login_event_repository import (  # noqa: E402
    RETENTION_DAYS,
    purge_expired_login_events,
)

# What the numbers below do and do not support. Printed with the report rather than
# left in a doc, because the misreading it guards against is the natural one and it
# happens at the moment someone looks at the total.
CAVEAT = f"""\
⚠️  WHAT THIS CAN AND CANNOT TELL YOU

  The demo account is shared, so every row carries the SAME user_id. It counts
  SIGN-INS, not people.

  It CAN tell you:      how many successful logins happened, and when — which days
                        were busy, whether interest continued after the first week,
                        whether anyone signs in at all any more.

  It CANNOT tell you:   how many distinct people used it, whether 120 logins are 40
                        people once or 3 people forty times, who anyone was, where
                        they were, what they did once inside, or how long they stayed.
                        A returning visitor and a first-time one are the same row.

  Sessions last {{token_hours}}h by default, so someone who stays signed in produces one
  event per {{token_hours}}h at most, however many times they open the app. Logins are a
  floor on visits, never a count of them.

  Failed attempts are not recorded, so this says nothing about people who tried the
  password and gave up. Events older than {RETENTION_DAYS} days are deleted, so the totals
  above are "in the last {RETENTION_DAYS} days", not "ever".
"""


def _describe_database() -> str:
    """The connection string with the password removed, so the output can be pasted."""
    from sqlalchemy.engine import make_url

    return make_url(DATABASE_URL).render_as_string(hide_password=True)


def _token_hours() -> int:
    """ACCESS_TOKEN_EXPIRE_MINUTES as hours, for the caveat. Read WITHOUT importing
    backend.core.security, which would demand a JWT_SECRET this script does not need."""
    import os

    raw = (os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES") or "").strip()
    try:
        minutes = int(raw) if raw else 1440
    except ValueError:
        minutes = 1440
    return max(1, round(minutes / 60))


def _table_missing() -> bool:
    """True when login_events does not exist yet, with an explanation printed.

    ⚠️ THIS SCRIPT CREATES NOTHING. scripts/claim_demo_user.py calls init_db() because
    it is a migration; this one only reports, and a read-only tool that quietly runs
    DDL against the production database someone pointed it at is a surprise nobody
    wants. The app builds the table at startup — so a missing table is a fact worth
    reporting, not a condition worth fixing from here.
    """
    if inspect(engine).has_table(LoginEvent.__tablename__):
        return False
    print(f"Database: {_describe_database()}\n")
    print(
        f"No {LoginEvent.__tablename__} table in this database yet.\n"
        "  The backend creates it on startup, so this means the app has not been "
        "started\n  against this database since login tracking was added. Start it "
        "once and try again."
    )
    return True


def _bar(count: int, largest: int, width: int = 32) -> str:
    if largest <= 0:
        return ""
    # At least one block for any non-zero day: a day with a login must not render as
    # a day without one.
    return "█" * max(1, round(count / largest * width))


def report(days: int | None) -> int:
    if _table_missing():
        return 0

    with SessionLocal() as db:
        query = db.query(LoginEvent)
        if days is not None:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            query = query.filter(LoginEvent.created_at >= since)
        events = query.order_by(LoginEvent.created_at.asc()).all()

        window = f"the last {days} days" if days is not None else f"the retained {RETENTION_DAYS} days"
        print(f"Database: {_describe_database()}")
        print(f"Window:   {window}\n")

        if not events:
            print("No successful logins recorded in this window.")
            print(
                "\nIf you expected some: the events table is only written by "
                "POST /auth/login,\nso a session that was already open when tracking "
                "was deployed has not\nproduced a row yet."
            )
            return 0

        print(f"Successful logins: {len(events)}")
        # Stored naive-UTC (see models/login_event.py), so it is labelled UTC rather
        # than converted to a local time it was never in.
        print(f"  first: {events[0].created_at:%Y-%m-%d %H:%M} UTC")
        print(f"  last:  {events[-1].created_at:%Y-%m-%d %H:%M} UTC")

        # Grouped in Python rather than SQL: date() in SQLite and date_trunc() in
        # Postgres are different functions, and one code path that works on both is
        # worth more than a GROUP BY over a table this size.
        by_day = Counter(event.created_at.date() for event in events)
        busiest = max(by_day.values())
        print(f"\nBy day (UTC) — {len(by_day)} day(s) with activity")
        for day in sorted(by_day):
            print(f"  {day}  {by_day[day]:>4}  {_bar(by_day[day], busiest)}")

        by_user = Counter(event.user_id for event in events)
        emails = {
            user.id: user.email
            for user in db.query(User).filter(User.id.in_(by_user)).all()
        }
        print("\nBy account")
        for user_id, count in by_user.most_common():
            print(f"  {count:>5}  {emails.get(user_id, '(deleted account)')}  [{user_id}]")

    print()
    print(CAVEAT.format(token_hours=_token_hours()))
    return 0


def prune() -> int:
    if _table_missing():
        return 0

    with SessionLocal() as db:
        # Deliberately NOT wrapped: unlike the write on the login path, a retention
        # failure that printed "done" would be the worst outcome here.
        deleted = purge_expired_login_events(db)
        remaining = db.query(LoginEvent).count()

    print(f"Database: {_describe_database()}")
    print(f"Deleted {deleted} event(s) older than {RETENTION_DAYS} days. {remaining} remain.")
    if deleted == 0:
        print("(The running app sweeps daily, so nothing to delete is the normal result.)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="login_activity",
        description="Count successful logins recorded against this database.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help=f"only count the last N days. Default: everything retained ({RETENTION_DAYS} days).",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help=f"delete events older than {RETENTION_DAYS} days and exit. The running app "
        "already does this daily; this is for a database no app is attached to.",
    )
    args = parser.parse_args(argv)

    if args.prune and args.days is not None:
        print("--prune and --days do nothing together; --prune ignores the window.", file=sys.stderr)
        return 1
    if args.days is not None and args.days <= 0:
        print("--days must be positive.", file=sys.stderr)
        return 1

    return prune() if args.prune else report(args.days)


if __name__ == "__main__":
    raise SystemExit(main())
