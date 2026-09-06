"""Couche Base de Données : persistance SQL pour la scalabilité RAG.

Remplace progressivement le stockage JSON plat par une base PostgreSQL
normalisée (3NF) préparée pour le support vectoriel (pgvector).

Phase 2.5 : découpage intelligent (``ChunkManager``) en deux passes
(structurelle avec hiérarchie de titres + récursive avec chevauchement)
et mode dédié aux dialogues (``speakers`` en métadonnées).
"""

from .chunker import (
    DEFAULT_CHUNK_MAX_CHARACTERS,
    DEFAULT_CHUNK_OVERLAP_CHARACTERS,
    ChunkManager,
    RAGChunk,
    chunk_markdown,
)
from .kim_parser import KimMessage, extract_kim_messages
from .manager import SQLDatabaseManager
from .models import (
    Base,
    GameEntityI18n,
    KimDialogue,
    LoreChunk,
    SyncStateRecord,
    WikiPage,
)

__all__ = [
    "Base",
    "WikiPage",
    "LoreChunk",
    "KimDialogue",
    "GameEntityI18n",
    "SyncStateRecord",
    "SQLDatabaseManager",
    "ChunkManager",
    "RAGChunk",
    "chunk_markdown",
    "DEFAULT_CHUNK_MAX_CHARACTERS",
    "DEFAULT_CHUNK_OVERLAP_CHARACTERS",
    "extract_kim_messages",
    "KimMessage",
]