import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class Pattern(Base):
    """A recurring behaviour observed across several answered post-mortems.

    Derived data: the whole set is deleted and rebuilt on each regeneration, so nothing
    here is a system of record. The post-mortems it cites are.
    """

    __tablename__ = "patterns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
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
