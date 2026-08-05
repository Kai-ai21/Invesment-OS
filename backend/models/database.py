import os

from sqlalchemy import create_engine
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
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
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
