import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class EvidenceEvent(Base):
    """Append-only log of AI evaluations of a claim against a document. Never updated or deleted."""

    __tablename__ = "evidence_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_id: Mapped[str] = mapped_column(String(36), ForeignKey("claims.id"), nullable=False)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False)
    verdict: Mapped[str] = mapped_column(String, nullable=False)  # "supports" | "contradicts" | "neutral"
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 to 1.0
    evidence_quote: Mapped[str] = mapped_column(Text, nullable=False)  # exact quote the AI cited
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)  # AI's short explanation
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
