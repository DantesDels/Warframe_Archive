"""Paragraph/section split from the cleaned content (RAG preparation)."""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .wiki_page import WikiPage


class LoreChunk(Base):
    """Paragraph/section split from the cleaned content (RAG preparation)."""

    __tablename__ = "lore_chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wiki_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wiki_pages.page_id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    # JSONB metadata (Phase 2.5): Markdown heading hierarchy
    # (Header 1/2/3) + speakers for dialogues.  Stored as JSONB on
    # PostgreSQL (generic JSON on other dialects for tests), GIN-indexed
    # for pre-vector filtering.
    # NB: the Python attribute is named `chunk_metadata` because `metadata`
    # is reserved by SQLAlchemy (schema MetaData); the DB column stays
    # `metadata`.
    chunk_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        server_default="{}",
    )
    # vector(1024) column — nullable until an embedding model fills it.
    # 1024 = actual dimension of the BGE-M3 GGUF model served by
    # LM Studio ("baai-bge-m3-568m"), aligned with init_db.sql.  The
    # pgvector type (via the 'pgvector' package) enables similarity search
    # (cosine ops) directly in SQL.
    embedding: Mapped[object | None] = mapped_column(Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    wiki_page: Mapped[WikiPage] = relationship(back_populates="lore_chunks")

    __table_args__ = (
        UniqueConstraint(
            "wiki_page_id", "chunk_index", name="uq_lore_chunks_page_index"
        ),
        # Parity with init_db.sql.
        Index("idx_chunks_page", "wiki_page_id"),
        Index("idx_chunks_metadata", "metadata", postgresql_using="gin"),
        Index(
            "idx_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
