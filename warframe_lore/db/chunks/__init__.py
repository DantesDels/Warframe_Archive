"""RAG chunking: public interface of the ``chunks`` sub-package.

Re-exports the ``ChunkManager``, the size constants, the ``RAGChunk`` type
and the legacy ``chunk_markdown`` API.

Implementation split between:
    * ``model``      -> ``RAGChunk`` + the size constants;
    * ``split``      -> ``ChunkManager`` (structural + dialogue);
    * ``sections``   -> heading blocks, section chain, context prefix;
    * ``splitters``  -> recursive split + overlap + hard cut;
    * ``speakers``   -> KIM speaker detection and dialogue metadata;
    * ``dialogue``   -> dialogue-mode chunking (whole sessions);
    * ``patterns``   -> purging of KIM navigation pointers;
    * ``adapters``   -> ``chunk_markdown`` / ``sections_from_markdown``.
"""

from __future__ import annotations

from .adapters import chunk_markdown, sections_from_markdown
from .model import (
    DEFAULT_CHUNK_MAX_CHARACTERS,
    DEFAULT_CHUNK_OVERLAP_CHARACTERS,
    DEFAULT_DIALOGUE_CHUNK_MAX_CHARACTERS,
    DEFAULT_DIALOGUE_CHUNK_OVERLAP_CHARACTERS,
    RAGChunk,
)
from .split import ChunkManager

__all__ = [
    "DEFAULT_CHUNK_MAX_CHARACTERS",
    "DEFAULT_CHUNK_OVERLAP_CHARACTERS",
    "DEFAULT_DIALOGUE_CHUNK_MAX_CHARACTERS",
    "DEFAULT_DIALOGUE_CHUNK_OVERLAP_CHARACTERS",
    "ChunkManager",
    "RAGChunk",
    "chunk_markdown",
    "sections_from_markdown",
]
