import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    thesis: Mapped["Thesis"] = relationship(back_populates="claims")
