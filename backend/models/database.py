import os

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.models.base import Base
from backend.models.alert import Alert  # noqa: F401 (registers mapper with Base)
from backend.models.claim import Claim  # noqa: F401 (registers mapper with Base)
from backend.models.document import Document  # noqa: F401 (registers mapper with Base)
from backend.models.evidence_event import EvidenceEvent  # noqa: F401 (registers mapper with Base)
from backend.models.holding import Holding  # noqa: F401 (registers mapper with Base)
from backend.models.pattern import Pattern  # noqa: F401 (registers mapper with Base)
from backend.models.post_mortem import PostMortem  # noqa: F401 (registers mapper with Base)
from backend.models.thesis import Thesis  # noqa: F401 (registers mapper with Base)
from backend.models.user import UNUSABLE_PASSWORD_HASH, User  # noqa: F401 (User registers mapper with Base)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "investment_os.db")
# The local-development fallback, and the source of truth for where the SQLite file
# lives — scripts/migrate_to_postgres.py reads it from here rather than rebuilding
# the path, so the two can never disagree about which file is being migrated.
SQLITE_URL = f"sqlite:///{DB_PATH}"


def normalise_database_url(raw: str) -> str:
    """Rewrite a deployment's DATABASE_URL into one SQLAlchemy 2.0 can actually open.

    Two separate corrections, and BOTH are needed on the same hosts:

    ⚠️ 1. `postgres://` IS NOT A SCHEME SQLALCHEMY ACCEPTS. It was removed as an
    alias in SQLAlchemy 1.4, so `create_engine` raises NoSuchModuleError ("Can't
    load plugin: sqlalchemy.dialects:postgres") on it. Heroku, Railway, Render and
    Fly all still hand out URLs in exactly that form, so the app would refuse to
    start on its first deploy with an error that reads like a missing package.

    ⚠️ 2. A BARE `postgresql://` LOADS psycopg2, WHICH IS NOT INSTALLED. SQLAlchemy's
    docs are explicit: "The PostgreSQL dialect uses psycopg2 as the default DBAPI."
    This project installs psycopg 3 (see requirements.txt), so an un-suffixed URL
    dies with ModuleNotFoundError: No module named 'psycopg2' — a failure that looks
    like a broken install rather than a URL that needed one word added to it. Naming
    the driver is what makes the dependency and the connection string agree.

    An explicit driver is left ALONE, including `postgresql+psycopg2://`. Someone who
    named a driver meant it, and silently overriding that would make the one escape
    hatch from this function invisible.

    Parsed with make_url rather than string surgery so the credentials, port and
    query string (`?sslmode=require`, which managed Postgres usually requires) all
    survive the rewrite untouched.
    """
    url = make_url(raw)

    if url.drivername == "postgres":
        # Backend AND driver, in one step: `postgres` alone is not loadable, so
        # correcting it to `postgresql` would only move the failure to point 2.
        return url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)

    if url.drivername == "postgresql":
        return url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)

    return raw


# Unset DATABASE_URL means local development, and local development is unchanged:
# the same SQLite file at the same path, opened the same way. An empty string counts
# as unset — a deployment that declares the variable and leaves it blank has not
# configured a database, and silently connecting to a container-local SQLite file
# that vanishes on the next restart is the worst possible reading of that.
DATABASE_URL = normalise_database_url(os.getenv("DATABASE_URL") or SQLITE_URL)

_IS_SQLITE = make_url(DATABASE_URL).get_backend_name() == "sqlite"

# ⚠️ check_same_thread IS A SQLITE DBAPI ARGUMENT AND ONLY THAT. Passed to psycopg it
# is a TypeError from connect(), so this cannot be unconditional. It exists because
# FastAPI serves requests from a thread pool while SQLite's driver defaults to
# refusing any connection used off the thread that opened it.
#
# pool_pre_ping is the mirror image: pointless against a local file, and close to
# mandatory against managed Postgres, where the pooler drops connections that have
# been idle and the first request after a quiet spell would otherwise 500 on a
# connection the pool still believes in.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _IS_SQLITE else {},
    pool_pre_ping=not _IS_SQLITE,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

    # ⚠️ GATED, BECAUSE BOTH OF THESE ARE WRITTEN IN SQLITE-ONLY SQL. They open with
    # `PRAGMA table_info(...)`, which Postgres rejects as a syntax error, so without
    # this branch the app would crash on startup against Postgres — every time, on
    # the very first call after create_all.
    #
    # Gating loses nothing. Both functions exist to bring an EXISTING SQLite file
    # up to the current model (see their own notes); a Postgres database is created
    # by create_all above with every column already present, so there is nothing for
    # them to migrate. The one thing they must not become is a general migration
    # mechanism with a dialect switch inside — when Postgres needs a real migration,
    # that is Alembic's job, not this function's.
    if _IS_SQLITE:
        _add_missing_user_auth_columns()
        _add_missing_pattern_owner_column()


def _add_missing_user_auth_columns() -> None:
    """Bring an EXISTING users table up to the current model. Idempotent.

    ⚠️ WITHOUT THIS, ADDING password_hash TO THE MODEL BREAKS THE WHOLE APP.
    `create_all` only ever CREATES missing tables — it does not alter tables that
    already exist. The live database has a users table from before authentication,
    so the column would exist in Python and not in SQLite, and every query touching
    User would fail with "no such column: users.password_hash". That table holds the
    demo@local row that owns all of the existing theses, holdings and alerts.

    This is a hand-rolled migration because the project has no Alembic. It is the
    narrowest thing that works: read the columns, add the one that is missing. When a
    second migration is needed, that is the moment to bring in Alembic rather than
    grow this function.

    The DEFAULT is what handles the passwordless legacy row — the existing user gets
    UNUSABLE_PASSWORD_HASH in the same statement that adds the column, so the table
    is never in a state where the NOT NULL is a lie.
    """
    with engine.begin() as connection:
        columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(users)")
        }
        if not columns:
            return  # No users table yet; create_all just built it from the model.
        if "password_hash" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN password_hash TEXT NOT NULL DEFAULT "
                f"'{UNUSABLE_PASSWORD_HASH}'"
            )
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"
        )


def _add_missing_pattern_owner_column() -> None:
    """Give an EXISTING patterns table its user_id. Idempotent.

    Same reasoning as _add_missing_user_auth_columns — `create_all` does not alter
    tables that already exist, so without this the column exists in Python and not in
    SQLite and every pattern query fails.

    ⚠️ EXISTING PATTERNS ARE BACKFILLED TO demo@local, NOT DELETED. They are derived
    data and regenerating them would be cheap, but they are derived from the user's
    own reflections and deleting rows to simplify a migration is not this migration's
    call to make. The empty-string default is a placeholder that exists only between
    the two statements below; the UPDATE immediately replaces it.
    """
    with engine.begin() as connection:
        columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(patterns)")
        }
        if not columns or "user_id" in columns:
            return

        connection.exec_driver_sql(
            "ALTER TABLE patterns ADD COLUMN user_id VARCHAR(36) NOT NULL DEFAULT ''"
        )
        connection.exec_driver_sql(
            "UPDATE patterns SET user_id = "
            "(SELECT id FROM users WHERE email = 'demo@local') "
            "WHERE user_id = '' "
            "AND EXISTS (SELECT 1 FROM users WHERE email = 'demo@local')"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_patterns_user_id ON patterns (user_id)"
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
