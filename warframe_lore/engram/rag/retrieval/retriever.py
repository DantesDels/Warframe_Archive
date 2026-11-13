"""RAG engine vector corpus access contract.

Abstraction (``typing.Protocol``): ``RAGService`` depends on this interface,
never on a concrete storage. ``CosinusSearch`` (PostgreSQL/pgvector) is one
implementation; others can be plugged in (FAISS, Qdrant...) by simple
substitution — without altering the engine core (O, D, L principles).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# Metagame chunks (patch notes, announcements) quote the same entities and
# eras as the lore: the story corpus must NEVER serve them (playtest Albrecht:
# Deep Archimedea modifiers, Netracell rewards in the tale).  The kind is read
# from ``StructuredChunk`` — ``None`` on the lore channel, always kept.
STORY_EXCLUDED_KINDS = ("game_updates", "game_announcements", "patch_notes")


@dataclass
class RAGHit:
    """A relevant passage found by vector search."""

    chunk_id: int
    page_title: str
    content: str
    score: float  # cosine similarity (1 - distance)
    kind: str | None = None  # structured table kind, None on the lore channel


@dataclass(frozen=True)
class DossierPage:
    """One page of a subject's dossier.

    ``more`` is True when the subject still has passages BEYOND this page: the
    narrative can be continued with unseen material instead of repeating what
    was already told.
    """

    hits: list[RAGHit]
    more: bool = False


@runtime_checkable
class Retriever(Protocol):
    """Searches for passages closest to a query vector."""

    async def search(self, query_vector: list[float]) -> list[RAGHit]:
        """Returns relevant passages (limited + score threshold)."""

    async def suggest_title(self, question: str) -> str | None:
        """Page title lexically close to the question, or None.

        Disambiguation fallback: used only when vector search returns no
        passage for the requested query.
        """


__all__ = ["DossierPage", "RAGHit", "Retriever", "STORY_EXCLUDED_KINDS"]
