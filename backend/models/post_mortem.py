import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class PostMortem(Base):
    """A prompt for the user to reflect on a thesis that broke, and their answer.

    Created PENDING — `prompt_question` is filled in later by the AI, and
    `user_response` stays NULL until the user actually answers. A row with a null
    `user_response` is an open question, which is what "pending" means everywhere
    in this codebase.
    """

    __tablename__ = "post_mortems"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    thesis_id: Mapped[str] = mapped_column(String(36), ForeignKey("theses.id"), nullable=False)
    # Nullable: a manually-requested post-mortem, or a thesis that broke without a
    # single identifiable core claim, has no specific claim to point at.
    broken_claim_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("claims.id"), nullable=True
    )
    # Filled in by the AI in Step 2; null until then.
    prompt_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Null means unanswered. This is the pending/answered flag.
    user_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The thesis status at the moment the break was detected, kept because the
    # thesis's own status keeps moving afterwards.
    status_at_break: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # One-way, like Alert: Thesis gains no `post_mortems` collection, so nothing that
    # loads a thesis today changes shape.
    thesis: Mapped["Thesis"] = relationship()  # noqa: F821 (resolved via the mapper registry)
    broken_claim: Mapped["Claim | None"] = relationship()  # noqa: F821

    @property
    def ticker(self) -> str:
        """A post-mortem is only ever read in the context of its ticker, so
        PostMortemOut carries it directly rather than making every caller join."""
        return self.thesis.ticker

    @property
    def broken_claim_statement(self) -> str | None:
        """The claim that broke, so the frontend needn't fetch the claim separately."""
        return self.broken_claim.statement if self.broken_claim is not None else None
