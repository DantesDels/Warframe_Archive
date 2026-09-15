"""A structured dialogue line (KIM, cinematic transcript or voice quote)."""

from __future__ import annotations

from datetime import datetime

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


class GameDialogue(Base):
    """One spoken line with human-readable context (quest, chapter, KIM)."""

    __tablename__ = "game_dialogues"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wiki_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wiki_pages.page_id", ondelete="CASCADE"), nullable=False
    )
    dialogue_kind: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 'kim' | 'cinematic' | 'quote'
    context: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # quest or character tag, human readable
    chapter: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # '##' heading of the scene
    speaker: Mapped[str] = mapped_column(Text, nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    player_choice: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    chemistry_gain: Mapped[bool] = mapped_column(
        # KIM '{Convo ends.}' marker = invisible in-game chemistry gain.
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    message_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    wiki_page: Mapped[WikiPage] = relationship(back_populates="game_dialogues")

    __table_args__ = (
        UniqueConstraint(
            "wiki_page_id", "message_order", name="uq_dialogue_page_order"
        ),
        Index("idx_dialogues_page", "wiki_page_id"),
        Index("idx_dialogues_kind", "dialogue_kind"),
    )
