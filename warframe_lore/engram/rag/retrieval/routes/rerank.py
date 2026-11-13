"""Re-ranking of the Codex route (simulated cross-encoding).

The route retrieves a hybrid candidate pool (vector + full-text); this stage
re-scores each candidate against the QUESTION itself, not against the query
vector, and keeps the ten most relevant passages.  A real cross-encoder
(BGE Reranker, ``bge-reranker-v2-m3``) plugs into the same :class:`Reranker`
port without touching the route.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from warframe_lore.engram.rag.retrieval.retriever import RAGHit
from warframe_lore.engram.rag.retrieval.scoring import query_terms


@runtime_checkable
class Reranker(Protocol):
    """Orders passages by relevance to the raw question."""

    def rank(self, query: str, hits: Sequence[RAGHit],
             top_n: int = 10) -> list[RAGHit]:
        """Return the ``top_n`` passages, most relevant first."""


@dataclass(frozen=True)
class SimulatedCrossEncoderReranker:
    """Deterministic stand-in for a neural cross-encoder.

    Scores the pair (question, passage) from lexical coverage and an exact
    phrase bonus, blended with the passage's retrieval score.  Deterministic,
    offline and cheap: it catches the lexical misses the vector channel makes
    while a real reranker stays optional.
    """

    semantic_weight: float = 0.6
    lexical_weight: float = 0.4
    phrase_bonus: float = 0.2

    def rank(self, query: str, hits: Sequence[RAGHit],
             top_n: int = 10) -> list[RAGHit]:
        terms = set(query_terms(query))
        if not terms:
            return list(hits)[:max(top_n, 1)]
        scored = sorted(
            ((self._score(query, terms, hit), hit) for hit in hits),
            key=lambda item: (-item[0], item[1].chunk_id),
        )
        return [hit for _, hit in scored[:max(top_n, 1)]]

    def _score(self, query: str, terms: set[str], hit: RAGHit) -> float:
        content = hit.content.casefold()
        coverage = len(terms & set(query_terms(content))) / len(terms)
        phrase = 1.0 if query.strip().casefold() in content else 0.0
        lexical = min(1.0, coverage + self.phrase_bonus * phrase)
        return (self.semantic_weight * max(0.0, min(1.0, hit.score))
                + self.lexical_weight * lexical)


__all__ = ["Reranker", "SimulatedCrossEncoderReranker"]
