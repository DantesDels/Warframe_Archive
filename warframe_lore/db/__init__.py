"""Database layer: SQL persistence for RAG scalability.

Progressively replaces the flat JSON storage with a normalized PostgreSQL
database (3NF) prepared for vector support (pgvector).

Phase 2.5: smart chunking (``ChunkManager``) in two passes (structural
with heading hierarchy + recursive with overlap) and a dedicated dialogue
mode (``speakers`` in metadata).
"""

from .chunks import (
    DEFAULT_CHUNK_MAX_CHARACTERS,
    DEFAULT_CHUNK_OVERLAP_CHARACTERS,
    ChunkManager,
    RAGChunk,
    chunk_markdown,
    sections_from_markdown,
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
    "sections_from_markdown",
    "DEFAULT_CHUNK_MAX_CHARACTERS",
    "DEFAULT_CHUNK_OVERLAP_CHARACTERS",
    "extract_kim_messages",
    "KimMessage",
]