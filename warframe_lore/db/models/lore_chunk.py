"""Paragraphe/section découpé du contenu nettoyé (préparation RAG)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from .base import Base
from .wiki_page import WikiPage


class LoreChunk(Base):
    """Paragraphe/section découpé du contenu nettoyé (préparation RAG)."""

    __tablename__ = "lore_chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True,
                                    autoincrement=True)
    wiki_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wiki_pages.page_id", ondelete="CASCADE"),
        nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    # Métadonnées JSONB (Phase 2.5) : hiérarchie des titres Markdown
    # (Header 1/2/3) + locuteurs pour les dialogues.  Stockées en JSONB sur
    # PostgreSQL (JSON générique sur les autres dialectes pour les tests),
    # indexées GIN pour le filtrage pré-vectoriel.
    # NB : l'attribut Python s'appelle `chunk_metadata` car `metadata` est
    # réservé par SQLAlchemy (MetaData du schéma) ; la colonne DB reste
    # `metadata`.
    chunk_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False, default=dict, server_default="{}")
    # Colonne vector(1024) — nullable jusqu'à ce qu'un modèle d'embedding la
    # remplisse.  1024 = dimension réelle du modèle BGE-M3 GGUF servi par
    # LM Studio ("baai-bge-m3-568m"), alignée sur init_db.sql.  Le type
    # pgvector (via le paquet 'pgvector') permet les recherches de similarité
    # (cosine ops) directement en SQL.
    embedding: Mapped[Optional[object]] = mapped_column(
        Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())

    wiki_page: Mapped[WikiPage] = relationship(back_populates="lore_chunks")

    __table_args__ = (
        UniqueConstraint("wiki_page_id", "chunk_index",
                         name="uq_lore_chunks_page_index"),
        # Parité avec init_db.sql.
        Index("idx_chunks_page", "wiki_page_id"),
        Index("idx_chunks_metadata", "metadata", postgresql_using="gin"),
        Index("idx_chunks_embedding", "embedding",
              postgresql_using="hnsw",
              postgresql_ops={"embedding": "vector_cosine_ops"}),
    )