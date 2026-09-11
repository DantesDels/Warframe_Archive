"""A message from a KIM conversation (parsed dialogue line)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .wiki_page import WikiPage


class KimDialogue(Base):
    """A message from a KIM conversation (parsed dialogue line)."""

    __tablename__ = "kim_dialogues"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True,
                                    autoincrement=True)
    wiki_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wiki_pages.page_id", ondelete="CASCADE"),
        nullable=False)
    message_order: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(Text, nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    player_choice: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false")
    timestamp: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())

    wiki_page: Mapped[WikiPage] = relationship(back_populates="kim_dialogues")

    __table_args__ = (
        UniqueConstraint("wiki_page_id", "message_order",
                         name="uq_kim_page_order"),
        Index("idx_kim_page", "wiki_page_id"),
    )