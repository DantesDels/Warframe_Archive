"""RAG chunking: public interface of the ``chunks`` sub-package.

Re-exports the ``ChunkManager``, the size constants, the ``RAGChunk`` type
and the legacy ``chunk_markdown`` API.

Implementation split between:
    * ``split``      — ``ChunkManager`` (structural + dialogue);
    * ``splitters``  — recursive splitters + overlap + speakers;
    * ``patterns``   — purging of KIM navigation pointers.
"""

from __future__ import annotations

from .split import (
    DEFAULT_CHUNK_MAX_CHARACTERS,
    DEFAULT_CHUNK_OVERLAP_CHARACTERS,
    DEFAULT_DIALOGUE_CHUNK_MAX_CHARACTERS,
    DEFAULT_DIALOGUE_CHUNK_OVERLAP_CHARACTERS,
    ChunkManager,
    RAGChunk,
    chunk_markdown,
)

__all__ = [
    "DEFAULT_CHUNK_MAX_CHARACTERS",
    "DEFAULT_CHUNK_OVERLAP_CHARACTERS",
    "DEFAULT_DIALOGUE_CHUNK_MAX_CHARACTERS",
    "DEFAULT_DIALOGUE_CHUNK_OVERLAP_CHARACTERS",
    "ChunkManager",
    "RAGChunk",
    "chunk_markdown",
]