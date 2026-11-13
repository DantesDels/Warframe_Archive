"""Route A (Codex): hybrid retrieval plus re-ranking.

Factual lookups need recall AND precision: the semantic channel (pgvector,
both corpora) catches paraphrases, the lexical channel (PostgreSQL FTS) catches
exact names a small embedding model can miss, and the reranker keeps the ten
passages that actually answer the question.  No chronological ordering here:
a Codex sheet is ranked by pure relevance.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Protocol

from warframe_lore.engram.rag.retrieval.model import HybridHit
from warframe_lore.engram.rag.retrieval.retriever import RAGHit, Retriever
from warframe_lore.engram.rag.retrieval.routes.rerank import Reranker
from warframe_lore.engram.rag.retrieval.scoring import strip_context_prefix

CODEX_TOP_N = 10
CODEX_LEXICAL_CANDIDATES = 24


class LexicalChannel(Protocol):
    """Full-text channel contract (implemented by ``HybridSearch``)."""

    async def lexical_hits(self, query: str,
                           candidates: int | None = None) -> list[HybridHit]:
        """Return the full-text matches, best first."""


class CodexRoute:
    """Vector + lexical union, reranked by relevance to the question."""

    def __init__(self, semantic: Retriever, lexical: LexicalChannel,
                 reranker: Reranker, top_n: int = CODEX_TOP_N,
                 lexical_candidates: int = CODEX_LEXICAL_CANDIDATES) -> None:
        self.semantic = semantic
        self.lexical = lexical
        self.reranker = reranker
        self.top_n = top_n
        self.lexical_candidates = lexical_candidates

    async def retrieve(self, question: str,
                       query_vector: list[float]) -> list[RAGHit]:
        """Hybrid candidate pool, then the ten most relevant passages."""
        semantic_hits, lexical_hits = await asyncio.gather(
            self.semantic.search(query_vector),
            self.lexical.lexical_hits(question, self.lexical_candidates),
        )
        fused = self._fuse(semantic_hits, lexical_hits)
        return self.reranker.rank(question, fused, top_n=self.top_n)

    @staticmethod
    def _fuse(semantic_hits: Sequence[RAGHit],
              lexical_hits: Sequence[HybridHit]) -> list[RAGHit]:
        """Union by passage identity, keeping the best channel score.

        ``max`` never lowers a score: a passage found by both channels must
        not fall under the relevance floor merely because it was fused.
        """
        fused: dict[tuple[str, str], RAGHit] = {
            (hit.page_title, strip_context_prefix(hit.content)): hit
            for hit in semantic_hits}
        for lexical in lexical_hits:
            key = (lexical.page_title, strip_context_prefix(lexical.content))
            existing = fused.get(key)
            lexical_score = lexical.ts_score or 0.0
            fused[key] = RAGHit(
                chunk_id=lexical.chunk_id,
                page_title=lexical.page_title,
                content=lexical.content,
                score=(max(existing.score, lexical_score)
                       if existing else lexical_score),
                kind=existing.kind if existing else None,
            )
        return list(fused.values())


__all__ = ["CODEX_LEXICAL_CANDIDATES", "CODEX_TOP_N", "CodexRoute",
           "LexicalChannel"]
