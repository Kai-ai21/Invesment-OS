import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class Alert(Base):
    """Raised when a thesis's status meaningfully changes."""

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    thesis_id: Mapped[str] = mapped_column(String(36), ForeignKey("theses.id"), nullable=False)
    prev_status: Mapped[str] = mapped_column(String, nullable=False)
    new_status: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # One-way on purpose: Thesis gains no `alerts` collection, so nothing that
    # loads a thesis today changes behaviour.
    thesis: Mapped["Thesis"] = relationship()  # noqa: F821 (resolved via the mapper registry)

    @property
    def ticker(self) -> str:
        """An alert is only ever read in the context of its ticker, so AlertOut
        carries it directly rather than making every caller join."""
        return self.thesis.ticker
