"""An in-game lore collectible (fragment / scroll / audio recording)."""

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


class LoreItem(Base):
    """One collectible piece of lore found in-game, with its author.

    ``series`` is the fragment category (e.g. "Glass Shard Fragments"),
    ``narrator`` the author of the text, ``item_text`` the written content
    and ``secret_text`` the hidden text unlocked by the player.
    """

    __tablename__ = "lore_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wiki_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wiki_pages.page_id", ondelete="CASCADE"), nullable=False
    )
    series: Mapped[str] = mapped_column(Text, nullable=False)
    item_name: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # quest the fragments relate to, if any
    planet: Mapped[str | None] = mapped_column(Text, nullable=True)
    narrator: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_text: Mapped[str] = mapped_column(Text, nullable=False)
    secret_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    wiki_page: Mapped[WikiPage] = relationship(back_populates="lore_items")

    __table_args__ = (
        UniqueConstraint("wiki_page_id", "item_name", name="uq_lore_item_name"),
        Index("idx_lore_items_page", "wiki_page_id"),
    )
