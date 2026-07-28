import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class Holding(Base):
    """A position the user actually owns.

    Deliberately NOT linked to a thesis. The two are independent: people hold things
    they never wrote a thesis about, and write theses on things they do not own yet.
    A holding is matched to a thesis by TICKER at read time (see portfolio_service), so
    neither can be orphaned by the other being deleted.
    """

    __tablename__ = "holdings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    shares: Mapped[float] = mapped_column(Float, nullable=False)
    # Average cost PER SHARE, not the total outlay — so adding to a position is one
    # edit to this number rather than a running total the user has to recompute.
    average_cost: Mapped[float] = mapped_column(Float, nullable=False)
    # Nullable: someone entering an existing portfolio often does not remember, and
    # refusing the holding over a forgotten date would be worse than not having it.
    purchased_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
