import uuid

from sqlalchemy import Boolean, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

# The vocabulary is defined ONCE, next to the field the model fills in. Retyping
# "checkable" as a literal here, again in the migration, again in the repository and
# again in the API schema is four places to disagree with each other — and the way
# that disagreement would surface is claims silently flagged, or silently not.
from backend.domain.claim import CHECKABLE
from backend.models.base import Base


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    thesis_id: Mapped[str] = mapped_column(String(36), ForeignKey("theses.id"), nullable=False)
    statement: Mapped[str] = mapped_column(String, nullable=False)
    proof_condition: Mapped[str] = mapped_column(String, nullable=False)
    break_condition: Mapped[str] = mapped_column(String, nullable=False)
    is_core: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)

    # Whether any filing or standard financial figure could EVER settle this claim's
    # conditions — see backend/domain/claim.py, which owns the meaning and the two
    # legal values. This is the extractor's judgement, stored so the UI can say so.
    #
    # ⚠️ NOT NULLABLE, AND THE DEFAULT IS CHECKABLE ON BOTH SIDES. Every claim written
    # before this column existed is checkable, because that is what the app assumed
    # about all of them and it is the reading that flags nobody falsely. A nullable
    # column would have meant a third state — "unlabelled" — that every reader would
    # have to decide how to render, and the honest rendering of it is "checkable"
    # anyway. `default` covers rows the ORM writes; `server_default` covers the
    # ALTER TABLE in models/database.py and anything else that inserts directly, so
    # the column can never hold NULL whichever path put the row there.
    verifiability: Mapped[str] = mapped_column(
        String, nullable=False, default=CHECKABLE, server_default=CHECKABLE
    )

    # One sentence naming the data that does not exist. Empty for checkable claims —
    # the same "does not apply" convention as EvidenceEvent's quote, not a NULL.
    verifiability_note: Mapped[str] = mapped_column(
        String, nullable=False, default="", server_default=text("''")
    )

    thesis: Mapped["Thesis"] = relationship(back_populates="claims")
