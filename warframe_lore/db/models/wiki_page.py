"""Root table ``wiki_pages``: one row per wiki page."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    # The relationships below are annotated with the CLASS NAMES (string form):
    # importing them for real would create a cycle between sibling modules, and
    # SQLAlchemy resolves them lazily once every model is registered.
    from .game_announcement import GameAnnouncement
    from .game_dialogue import GameDialogue
    from .game_quest import GameQuest
    from .game_update import GameUpdate
    from .kim_dialogue import KimDialogue
    from .lore_chunk import LoreChunk
    from .lore_item import LoreItem
    from .warframe import Warframe


class WikiPage(Base):
    """Root table: one row per wiki page (native page_id = PK)."""

    __tablename__ = "wiki_pages"

    page_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )
    page_title: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    namespace: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_updated: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    touched: Mapped[str | None] = mapped_column(Text, nullable=True)
    canon_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="canon", server_default="canon"
    )
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # A unique index on the title (find a page by title, fast).
    __table_args__ = (
        # The allowed values mirror the output statuses.
        CheckConstraint(
            "canon_status IN ('canon', 'speculation', 'community_theory')",
            name="ck_wiki_pages_canon_status",
        ),
        # Parity with init_db.sql: finding a page by title (+ filter
        # bucket/status) must go through indexes declared in the ORM.
        Index("idx_wiki_pages_title", "page_title", unique=True),
        Index("idx_wiki_pages_bucket", "category"),
        Index("idx_wiki_pages_canon", "canon_status"),
    )

    lore_chunks: Mapped[list[LoreChunk]] = relationship(
        back_populates="wiki_page", cascade="all, delete-orphan"
    )
    kim_dialogues: Mapped[list[KimDialogue]] = relationship(
        back_populates="wiki_page", cascade="all, delete-orphan"
    )
    game_dialogues: Mapped[list[GameDialogue]] = relationship(
        back_populates="wiki_page", cascade="all, delete-orphan"
    )
    lore_items: Mapped[list[LoreItem]] = relationship(
        back_populates="wiki_page", cascade="all, delete-orphan"
    )
    warframes: Mapped[list[Warframe]] = relationship(
        back_populates="wiki_page", cascade="all, delete-orphan"
    )
    game_quests: Mapped[list[GameQuest]] = relationship(
        back_populates="wiki_page", cascade="all, delete-orphan"
    )
    game_updates: Mapped[list[GameUpdate]] = relationship(
        back_populates="wiki_page", cascade="all, delete-orphan"
    )
    game_announcements: Mapped[list[GameAnnouncement]] = relationship(
        back_populates="wiki_page", cascade="all, delete-orphan"
    )
