"""Quest index entry (main or side quest)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .wiki_page import WikiPage


class GameQuest(Base):
    """One quest with its type, release note and short description.

    ``quest_type`` is ``main`` or ``side``; ``release_note`` keeps the
    raw "released in <...>" phrasing (update number or hotfix date).
    """

    __tablename__ = "game_quests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wiki_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wiki_pages.page_id", ondelete="CASCADE"), nullable=False
    )
    quest_name: Mapped[str] = mapped_column(Text, nullable=False)
    quest_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    release_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    quest_context: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # one-line description / synopsis
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    wiki_page: Mapped[WikiPage] = relationship(back_populates="game_quests")

    __table_args__ = (
        UniqueConstraint("wiki_page_id", name="uq_game_quest_page"),
        Index("idx_quests_type", "quest_type"),
    )
