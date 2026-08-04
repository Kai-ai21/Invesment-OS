import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base

# The password_hash of an account that CANNOT BE LOGGED INTO.
#
# ⚠️ THIS IS NOT A HASH AND IS NOT MEANT TO BE ONE. "!" is the long-standing Unix
# convention for a locked account, and it is deliberately not valid bcrypt output:
# bcrypt.checkpw raises on it rather than returning False, and verify_password turns
# that into a plain False. So no password on earth verifies against it — including,
# importantly, the empty string.
#
# It exists for one row: the seeded demo@local user, which predates authentication
# and owns all the existing data. See seed_demo_user in models/database.py for why
# this was chosen over making the column nullable.
UNUSABLE_PASSWORD_HASH = "!"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # ⚠️ NOT NULL, with locked accounts carrying UNUSABLE_PASSWORD_HASH rather than
    # NULL. A nullable password_hash would mean every login path has to ask "is this
    # one of the passwordless ones?", and the day someone writes that check as
    # `if user.password_hash is None or verify(...)` it is an authentication bypass
    # on every legacy row. There is no such branch to get wrong if the column cannot
    # be null: an unusable value fails the same comparison every real password does.
    #
    # ⚠️ THE DEFAULT IS LOCKED, AND IT IS A SAFETY PROPERTY RATHER THAN A
    # CONVENIENCE. `User(email=...)` with no password — which is how every fixture
    # and seed in this repo builds one — yields an account that CANNOT be logged
    # into. The alternative defaults are all worse: no default at all turns a
    # forgotten argument into a 500, and any real hash as a default would mean a
    # forgotten argument silently creates an account with a password the author of
    # that default knows. Omitting the password can only ever fail closed.
    password_hash: Mapped[str] = mapped_column(
        String, nullable=False, default=UNUSABLE_PASSWORD_HASH
    )
