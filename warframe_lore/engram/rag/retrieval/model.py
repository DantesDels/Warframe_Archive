"""Data contract of the hybrid search (RAG Inspector).

Single responsibility: the two shapes returned to the API and the UI — one hit
with its per-channel scores and chunk metadata, and the query envelope carrying
the alias context.  No SQLAlchemy here: the contract is importable anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HybridHit:
    """One retrieved chunk with its per-channel scores and metadata."""

    chunk_id: int
    page_title: str
    content: str
    chunk_metadata: dict[str, Any]
    section: str = ""
    cosine_score: float | None = None
    ts_score: float | None = None
    headline: str = ""
    score: float = 0.0


@dataclass
class HybridQuery:
    """Result of a hybrid search: alias context + retrieved hits."""

    query: str                          # raw user wording (prompt question)
    search_question: str                # what was embedded / full-text searched
    alias_note: str
    canonical: str
    terms: list[str] = field(default_factory=list)
    hits: list[HybridHit] = field(default_factory=list)

    @property
    def alias_active(self) -> bool:
        """True when the alias middleware rewrote the query."""
        return bool(self.alias_note)


__all__ = ["HybridHit", "HybridQuery"]
