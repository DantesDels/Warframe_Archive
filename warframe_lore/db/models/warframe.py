"""Warframe index entry (base or Prime), from the official site."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .wiki_page import WikiPage


class Warframe(Base):
    """One row of the warframe directory (catalog / index only).

    ``frame_name`` is the base name ("Ash"); ``is_prime`` selects the
    variant.  ``description`` holds the official French blurb.
    """

    __tablename__ = "warframes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wiki_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wiki_pages.page_id", ondelete="CASCADE"), nullable=False
    )
    frame_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_prime: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    wiki_page: Mapped[WikiPage] = relationship(back_populates="warframes")

    __table_args__ = (
        UniqueConstraint("frame_name", "is_prime", name="uq_warframe_variant"),
    )
