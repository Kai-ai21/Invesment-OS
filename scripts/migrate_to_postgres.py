#!/usr/bin/env python
"""Copy every row from the local SQLite file into the Postgres database in DATABASE_URL.

A ONE-OFF, not a tool. Run it once when moving a local database to a deployed one and
then forget it exists. It is deliberately not idempotent and not resumable: it refuses
to touch a target that already holds anything (see _refuse_if_target_has_data), because
the alternative — merging into a live database — is a different and much harder job
that nothing here is trying to do.

⚠️ IDS ARE COPIED, NEVER REGENERATED. Every primary key in this schema is a
String(36) UUID produced in Python, and every foreign key stores that same string.
There are no integer sequences anywhere, which is the single fact that makes this
script short: nothing has to be remapped, nothing has to be re-parented, and no
Postgres sequence has to be fast-forwarded afterwards. A row arrives with the id it
left with, so every reference to it still resolves.

⚠️ IT GOES THROUGH SQLALCHEMY CORE ON BOTH ENDS, ON PURPOSE — not sqlite3 to raw
INSERT. Reading through the same Table objects the app uses means each dialect's type
handling does the conversions that would otherwise be hand-written and forgotten:

  - JSON      patterns.evidence_post_mortem_ids is TEXT in SQLite and json in
              Postgres. The SQLite result processor parses it to a Python list and
              the Postgres bind processor re-encodes it, so the value crosses as a
              list. A raw copy would insert the SQLite string and store a JSON
              document that is a quoted string rather than an array.
  - BOOLEAN   SQLite has none; is_read and dismissed are 0/1 integers there. Postgres
              rejects an integer for a boolean column outright. The Boolean type
              converts both ways.
  - DATETIME  Both sides declare DateTime with no timezone, so naive values move
              across verbatim. This is intentional: the timezone debt in this schema
              is real (the app writes aware UTC into naive columns) but a data copy
              is the wrong place to start rewriting timestamps, and doing it silently
              would be worse than leaving it. Values arrive exactly as stored.

USAGE
    DATABASE_URL='postgresql+psycopg://user:pass@host:5432/dbname' \\
        python -m scripts.migrate_to_postgres

    python -m scripts.migrate_to_postgres --dry-run   # counts and checks, no writes

The source is always the SQLite file the app falls back to locally; its path comes
from backend.models.database so the two cannot disagree about which file that is.
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import OperationalError

from backend.models.database import DB_PATH, SQLITE_URL, normalise_database_url
from backend.models.base import Base

# Rows per INSERT. Large enough that the round trips do not dominate on a remote
# database, small enough that a wide table (documents.raw_text holds whole filings)
# never builds a parameter list big enough to matter.
BATCH = 500


def _fail(message: str) -> int:
    """One exit path for every refusal, so nothing ever half-runs.

    Every refusal below is checked BEFORE the single transaction that does the
    writing, and each one prints what to do about it rather than a traceback.
    """
    print(f"Refusing to run: {message}", file=sys.stderr)
    return 1


def _resolve_target() -> str | None:
    """The Postgres URL to write to, or None if the environment does not name one.

    Runs DATABASE_URL through the same normaliser the app uses, so a `postgres://`
    URL pasted from a managed host is accepted here for exactly the same reasons it
    is accepted there — and so a URL that works for the migration cannot then fail
    for the application.
    """
    raw = os.getenv("DATABASE_URL") or ""
    return normalise_database_url(raw) if raw.strip() else None


def _count(engine_or_conn, table) -> int:
    return engine_or_conn.execute(select(func.count()).select_from(table)).scalar_one()


def _occupied_tables(conn, tables) -> list[str]:
    """Names of target tables that already hold rows. Empty means safe to proceed.

    ⚠️ THE CHECK IS "ANY ROW ANYWHERE", not "any row that would collide". A target
    with data in it is a database somebody is already using, and this script has no
    idea whether the ids about to arrive would overwrite it, duplicate it or merely
    sit beside it. The only safe reading of a non-empty target is that the operator
    pointed at the wrong database.

    ⚠️ COUNTS ONLY TABLES THAT ALREADY EXIST, which is what lets this run BEFORE
    create_all rather than after. Counting a table Postgres has never heard of raises
    UndefinedTable, so the obvious ordering — create the schema, then check it is
    empty — forces a schema to be written before the script has established it is
    allowed to write anything. A table that does not exist holds no rows; that is the
    same answer without the DDL.
    """
    existing = set(inspect(conn).get_table_names())
    return [t.name for t in tables if t.name in existing and _count(conn, t) > 0]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy the local SQLite database into the Postgres DATABASE_URL."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report source counts and run every safety check, but write nothing.",
    )
    args = parser.parse_args()

    # ---- resolve and validate both ends, before anything is opened for writing ----

    target_url = _resolve_target()
    if target_url is None:
        return _fail(
            "DATABASE_URL is not set. Point it at the Postgres database to migrate "
            "INTO, e.g.\n"
            "    DATABASE_URL='postgresql+psycopg://user:pass@host:5432/dbname' "
            "python -m scripts.migrate_to_postgres"
        )

    if make_url(target_url).get_backend_name() != "postgresql":
        return _fail(
            f"DATABASE_URL is not a Postgres URL (got {make_url(target_url).drivername!r}). "
            "This script only copies SQLite -> Postgres; there is nothing sensible for "
            "it to do with any other target."
        )

    if not os.path.exists(DB_PATH):
        return _fail(
            f"no SQLite database at {DB_PATH}. That is the file this script copies FROM, "
            "and it does not exist — there is nothing to migrate."
        )

    source_engine: Engine = create_engine(SQLITE_URL)
    target_engine: Engine = create_engine(target_url)

    # sorted_tables is dependency-ordered by foreign key, which is exactly the order
    # the inserts have to happen in: users before theses, theses before claims,
    # claims and documents before evidence_events. Deriving it from the metadata
    # rather than hand-listing means a table added to the app later is ordered
    # correctly here without anyone remembering to come back.
    tables = list(Base.metadata.sorted_tables)

    # A table the app knows about that the SQLite file predates is reported rather
    # than skipped in silence — "0 rows" and "no such table" are different facts and
    # the operator should see which one they are looking at.
    source_tables = set(inspect(source_engine).get_table_names())
    missing = [t.name for t in tables if t.name not in source_tables]

    # Anything in the SQLite file that is NOT part of the app's schema. Nothing is
    # copied for these — but staying quiet about them would be how a table quietly
    # fails to arrive.
    unknown = sorted(source_tables - {t.name for t in tables} - {"sqlite_sequence"})

    print(f"source: {SQLITE_URL}")
    print(f"target: {make_url(target_url).render_as_string(hide_password=True)}")
    print()

    # ---- source counts -----------------------------------------------------------

    with source_engine.connect() as source_conn:
        source_counts = {
            table.name: (0 if table.name in missing else _count(source_conn, table))
            for table in tables
        }

    print("BEFORE (source)")
    for name, count in source_counts.items():
        note = "   [absent in source]" if name in missing else ""
        print(f"  {name:<18} {count:>7}{note}")
    print(f"  {'TOTAL':<18} {sum(source_counts.values()):>7}")
    if unknown:
        print(f"\n  not part of the app schema, NOT copied: {', '.join(unknown)}")
    print()

    # ---- emptiness check on the target, BEFORE any DDL ---------------------------

    # ⚠️ THE EMPTINESS CHECK RUNS BEFORE create_all, NOT AFTER. Creating the schema is
    # itself a write, and a script whose headline promise is "refuses to run if the
    # target already has data" must not have already modified that database by the
    # time it decides to refuse. It is also what makes --dry-run honest: the dry run
    # reaches this point, reports, and exits having issued nothing but SELECTs.
    try:
        with target_engine.connect() as target_conn:
            occupied = _occupied_tables(target_conn, tables)
    except OperationalError as exc:
        # By far the most likely failure in real use — wrong host, firewall, missing
        # sslmode, database not created yet. The bare traceback for this is forty
        # lines of SQLAlchemy internals wrapped around one sentence that matters.
        return _fail(
            "could not connect to the target Postgres database.\n"
            f"  {make_url(target_url).render_as_string(hide_password=True)}\n"
            f"  {exc.orig}\n"
            "Check the host, port and credentials, that the database exists, and that "
            "your provider does not require ?sslmode=require."
        )

    if occupied:
        return _fail(
            "the target database already has data, in: " + ", ".join(occupied) + ".\n"
            "This script only ever populates an EMPTY database — it does not merge, "
            "and it will not overwrite. Check that DATABASE_URL points where you think "
            "it does; if it does and you really mean to replace what is there, drop "
            "those tables yourself first."
        )

    if args.dry_run:
        print(
            "--dry-run: target reachable and empty, every check passed.\n"
            "Nothing was written — no tables were created and no rows were copied."
        )
        return 0

    # Committed separately from the copy below, so a failed copy leaves an empty
    # schema that a re-run can fill rather than a half-built database.
    Base.metadata.create_all(bind=target_engine)

    # ---- the copy ----------------------------------------------------------------

    # ONE transaction for every table. A failure anywhere — a type that will not
    # convert, a foreign key that does not resolve, a dropped connection — leaves the
    # target exactly as empty as it started, which is the only state this script can
    # safely leave behind other than "finished".
    with target_engine.begin() as target_conn:
        with source_engine.connect() as source_conn:
            for table in tables:
                if table.name in missing:
                    continue

                copied = 0
                result = source_conn.execute(select(table))
                for chunk in result.mappings().partitions(BATCH):
                    rows = [dict(row) for row in chunk]
                    if not rows:
                        continue
                    target_conn.execute(table.insert(), rows)
                    copied += len(rows)

                print(f"  copied {table.name:<18} {copied:>7}")

        # ---- verify, INSIDE the transaction ---------------------------------------

        # Counted before the commit on purpose: a mismatch raises, the `begin()` block
        # rolls back, and the target is left empty rather than holding a partial copy
        # that looks finished.
        print()
        print("AFTER (target)")
        mismatches: list[str] = []
        for table in tables:
            expected = source_counts[table.name]
            actual = _count(target_conn, table)
            flag = ""
            if actual != expected:
                flag = f"   MISMATCH (expected {expected})"
                mismatches.append(f"{table.name}: expected {expected}, got {actual}")
            print(f"  {table.name:<18} {actual:>7}{flag}")

        if mismatches:
            raise SystemExit(
                "\nROW COUNTS DO NOT MATCH — rolling back, nothing was written:\n  "
                + "\n  ".join(mismatches)
            )

    print(f"\nDone. {sum(source_counts.values())} rows copied, every table matched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
