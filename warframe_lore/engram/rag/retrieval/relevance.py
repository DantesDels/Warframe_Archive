"""Relevance decisions of a RAG retrieval (pure — no I/O, no provider).

Single responsibility: the rules that keep an untrusted passage away from the
LLM — the ONE relevance floor (single source of truth for both configured
thresholds), the passages kept above it, and the entity-lookup guard (a named
target absent from every passage cannot be answered by the archives).
"""

from __future__ import annotations

from ..query.query_guard import _lookup_entity
from .retriever import RAGHit


def relevance_floor(suggestion_min_score: float,
                    critical_min_score: float | None) -> float:
    """The single relevance floor: the strictest of the two thresholds.

    ``critical_min_score`` defaults to the disambiguation threshold, so one
    value governs both "suggest another title" and "never call the LLM".
    """
    if critical_min_score is None:
        return suggestion_min_score
    return max(critical_min_score, suggestion_min_score)


def keep_relevant(hits: list[RAGHit], minimum: float) -> list[RAGHit]:
    """Passages at or above the floor, order preserved (best first).

    Filtering happens BEFORE any ranking use, so the top score reflects the
    strength of the best RETAINED passage — never an off-topic neighbour.
    """
    return [hit for hit in hits if hit.score >= minimum]


def missing_entity(question: str, hits: list[RAGHit]) -> str | None:
    """Named entity of a "qui est X" question absent from EVERY passage.

    Playtest "Qui est Vena ?": the archives cannot support an answer about an
    entity they never mention, so the caller short-circuits instead of letting
    the model invent a biography.  ``None`` = supported (or no entity named).
    """
    entity = _lookup_entity(question)
    if not entity or not hits:
        return None
    passages = " ".join(hit.content for hit in hits).lower()
    return None if entity.lower() in passages else entity


__all__ = ["keep_relevant", "missing_entity", "relevance_floor"]
