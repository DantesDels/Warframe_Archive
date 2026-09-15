"""A message from a KIM conversation (parsed dialogue line)."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .wiki_page import WikiPage


class KimDialogue(Base):
    """A message from a KIM conversation (parsed dialogue line)."""

    __tablename__ = "kim_dialogues"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wiki_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wiki_pages.page_id", ondelete="CASCADE"), nullable=False
    )
    context: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # quest or character tag, human readable
    chapter: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # '##' heading of the scene
    message_order: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(Text, nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    player_choice: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    chemistry_gain: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    parent_message_id: Mapped[int | None] = mapped_column(
        # Adjacency-list edge: previous message / branching NPC parent.
        BigInteger,
        ForeignKey("kim_dialogues.id", ondelete="SET NULL"),
        nullable=True,
    )

    wiki_page: Mapped[WikiPage] = relationship(back_populates="kim_dialogues")

    __table_args__ = (
        UniqueConstraint("wiki_page_id", "message_order", name="uq_kim_page_order"),
        Index("idx_kim_page", "wiki_page_id"),
        Index("idx_kim_parent", "parent_message_id"),
    )
