"""RAGChunk and the default chunk size constants.

Single responsibility: the chunk document type returned by
:class:`~warframe_lore.db.ChunkManager` and the sizing defaults
(Phase 2.5 targets).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Target size (in characters) by default - Pitch Phase 2.5: 1000-1500.
DEFAULT_CHUNK_MAX_CHARACTERS = 1200
# Default overlap - Pitch Phase 2.5: 150-200.
DEFAULT_CHUNK_OVERLAP_CHARACTERS = 175
# Target size for dialogues (whole sessions, preserved context).
DEFAULT_DIALOGUE_CHUNK_MAX_CHARACTERS = 2500
DEFAULT_DIALOGUE_CHUNK_OVERLAP_CHARACTERS = 250


@dataclass(frozen=True)
class RAGChunk:
    """A chunk ready for embedding / RAG storage."""

    chunk_index: int
    content_markdown: str
    # JSONB metadata: heading hierarchy (Header 1/2/3) + speakers.
    metadata: dict[str, Any] = field(default_factory=dict)
