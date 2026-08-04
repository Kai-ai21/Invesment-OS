import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class Pattern(Base):
    """A recurring behaviour observed across several answered post-mortems.

    Derived data: the whole set is deleted and rebuilt on each regeneration, so nothing
    here is a system of record. The post-mortems it cites are.
    """

    __tablename__ = "patterns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # ⚠️ ADDED IN A2, AND THE ONLY TABLE THAT NEEDED A NEW COLUMN TO BE SCOPED AT ALL.
    # Every other user-owned row reaches a user through a foreign key that already
    # existed — a claim through its thesis, an alert through its thesis. A pattern
    # cites post-mortems in a JSON list, which is not a join and cannot be filtered
    # on, so before this column there was no query that could tell one user's
    # patterns from another's. The practical consequence was worse than disclosure:
    # delete_all_patterns() ran unfiltered on every regeneration, so the second user
    # to press "Analyse" would have deleted the first user's patterns.
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    # A plain JSON list rather than a join table: patterns are rebuilt wholesale, never
    # queried BY post-mortem, and a row is meaningless without its citations. The API
    # resolves these ids to tickers and questions when it serves them.
    evidence_post_mortem_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    # Dismissed patterns are kept rather than deleted so a regeneration can be compared
    # against what the user has already rejected.
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
