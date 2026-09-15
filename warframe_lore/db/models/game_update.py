"""PC patch-note entry (update or hotfix)."""

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


class GameUpdate(Base):
    """One patch-note page (version, title, type, date and summary).

    ``version`` is the dotted form of the URL slug ("39.0.0"),
    ``update_type`` keeps the official label ("Mise à jour principale"
    or "Correctif") and ``release_date`` the human-readable date.
    """

    __tablename__ = "game_updates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wiki_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wiki_pages.page_id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(Text, nullable=False)
    update_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    update_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    release_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform: Mapped[str] = mapped_column(
        Text, nullable=False, default="pc", server_default="pc"
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    wiki_page: Mapped[WikiPage] = relationship(back_populates="game_updates")

    __table_args__ = (
        UniqueConstraint("wiki_page_id", name="uq_game_update_page"),
        Index("idx_updates_version", "version"),
    )
