"""Modèles SQLAlchemy 2.0 correspondant au schéma ``init_db.sql``.

Trois tables métier (page + chunks + dialogues KIM) et une table d'état
de synchronisation (delta).  L'usage est **async** (asyncpg).

Gardez ces modèles synchronisés avec ``init_db.sql`` : les noms de tables
et de colonnes, les types, les contraintes et les clés étrangères doivent
rester identiques des deux côtés.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    """Base déclarative commune à tous les modèles."""


class WikiPage(Base):
    """Table racine : une ligne par page de wiki (page_id natif = PK)."""

    __tablename__ = "wiki_pages"

    page_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    page_title: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    namespace: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0")
    last_updated: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)
    touched: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    canon_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="canon", server_default="canon")
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())

    # Un index unique sur le titre (retrouver une page par titre, vite).
    __table_args__ = (
        # Les valeurs autorisées sont calquées sur les statuts de sortie.
        CheckConstraint(
            "canon_status IN ('canon', 'speculation', 'community_theory')",
            name="ck_wiki_pages_canon_status"),
    )

    lore_chunks: Mapped[list["LoreChunk"]] = relationship(
        back_populates="wiki_page", cascade="all, delete-orphan")
    kim_dialogues: Mapped[list["KimDialogue"]] = relationship(
        back_populates="wiki_page", cascade="all, delete-orphan")


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
    # Colonne vector(384) — nullable jusqu'à ce qu'un modèle d'embedding la
    # remplisse.  Le type pgvector (via le paquet 'pgvector') permet de faire
    # des recherches de similarité (cosine ops) directement en SQL.
    embedding: Mapped[Optional[object]] = mapped_column(
        Vector(384), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())

    wiki_page: Mapped[WikiPage] = relationship(back_populates="lore_chunks")

    __table_args__ = (
        UniqueConstraint("wiki_page_id", "chunk_index",
                         name="uq_lore_chunks_page_index"),
    )


class KimDialogue(Base):
    """Un message d'une discussion KIM (ligne de dialogue parsée)."""

    __tablename__ = "kim_dialogues"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True,
                                    autoincrement=True)
    wiki_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wiki_pages.page_id", ondelete="CASCADE"),
        nullable=False)
    message_order: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(Text, nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    player_choice: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false")
    timestamp: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())

    wiki_page: Mapped[WikiPage] = relationship(back_populates="kim_dialogues")

    __table_args__ = (
        UniqueConstraint("wiki_page_id", "message_order",
                         name="uq_kim_page_order"),
    )


class GameEntityI18n(Base):
    """Entité du jeu localisée, issue du Warframe Public Export.

    Une ligne par couple (entité, langue) ; se nourrit des fichiers JSON des
    manifests officiels (``index_<lang>.txt.lzma``).
    """

    __tablename__ = "game_entities_i18n"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True,
                                    autoincrement=True)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lang: Mapped[str] = mapped_column(Text, nullable=False, default="en",
                                      server_default="en")
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("entity_id", "lang", name="uq_entities_id_lang"),
    )


class SyncStateRecord(Base):
    """État du mode delta (remplace ``sync_state.json`` local).

    Compare le ``touched`` de l'API au dernier ``touched`` stocké ici pour
    décider si une page doit être re-téléchargée.
    """

    __tablename__ = "sync_state"

    bucket_id: Mapped[str] = mapped_column(Text, primary_key=True)
    page_title: Mapped[str] = mapped_column(Text, primary_key=True)
    page_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    touched: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
