"""Embedded chunk from a human-readable structured table (RAG corpus)."""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class StructuredChunk(Base):
    """One embedded row from the 6 human-readable element tables.

    ``kind`` identifies the source table (``warframes``, ``game_quests``, etc.),
    ``source_id`` the PK in that table, and ``content`` the rendered text fed
    to bge-m3.  The cosine search merges these with ``lore_chunks``.
    """

    __tablename__ = "structured_chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    wiki_page_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("wiki_pages.page_id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    embedding: Mapped[object | None] = mapped_column(Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("kind", "source_id", name="uq_structured_kind_source"),
        Index("idx_structured_kind", "kind"),
        Index("idx_structured_page", "wiki_page_id"),
        Index(
            "idx_structured_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
