"""Abstract contracts for vector and hybrid retrieval.

Exposes :class:`Retriever`, :class:`RAGHit` and :class:`DossierPage`
as central interfaces for dependency inversion.
"""

from __future__ import annotations

from warframe_lore.engram.rag.retrieval.retriever import (
    STORY_EXCLUDED_KINDS,
    DossierPage,
    RAGHit,
    Retriever,
)

__all__ = ["DossierPage", "RAGHit", "Retriever", "STORY_EXCLUDED_KINDS"]

