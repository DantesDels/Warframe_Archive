"""Hybrid search over ``lore_chunks``: pgvector cosine + PostgreSQL FTS.

Backend of the "RAG Inspector" UI: one query runs across BOTH channels and the
raw per-channel scores are surfaced for every chunk, so an operator can audit
what a RAG call would ground on.  The semantic channel embeds the alias-expanded
query (exactly like ``RAGService.retrieve``); the lexical channel runs French
full-text.  This module only orchestrates — SQL in :mod:`statements`, scores in
:mod:`scoring`, result shapes in :mod:`model`.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker

from warframe_lore.engram.llm import EmbeddingProvider
from warframe_lore.engram.rag.query.aliases import AliasResolver
from warframe_lore.engram.rag.retrieval.model import HybridHit, HybridQuery
from warframe_lore.engram.rag.retrieval.scoring import (
    fuse,
    query_terms,
    section_label,
    strip_context_prefix,
    ts_rank_normalized,
)
from warframe_lore.engram.rag.retrieval.search import set_hnsw_ef_search
from warframe_lore.engram.rag.retrieval.statements import (
    cosine_statement,
    fts_statement,
)


class HybridSearch:
    """Runs both retrieval channels and fuses the hits (read-only)."""

    def __init__(self, sessions: async_sessionmaker,
                 embeddings: EmbeddingProvider,
                 alias_resolver: AliasResolver | None = None,
                 candidates: int = 24) -> None:
        self.sessions = sessions
        self.embeddings = embeddings
        self.alias_resolver = alias_resolver or AliasResolver()
        # Per-channel candidate count must exceed the requested limit so the
        # lexical/semantic fusion has a real pool to pick from.
        self.candidates = candidates

    async def search(self, question: str, limit: int = 12) -> HybridQuery:
        """Resolve aliases, embed the expanded query, retrieve both channels
        and return the fused, ranked hits."""
        expanded, alias_note, canonical = (
            self.alias_resolver.resolve(question.strip()))
        result = HybridQuery(
            query=question.strip(),
            search_question=expanded,
            alias_note=alias_note,
            canonical=canonical,
            terms=query_terms(expanded),
        )
        if not result.search_question:
            return result

        query_vector = (await self.embeddings.embed([expanded]))[0]
        async with self.sessions() as session:
            hits = await self._both_channels(session, expanded, query_vector)
        result.hits = sorted(hits.values(), key=lambda h: h.score,
                             reverse=True)[:max(limit, 1)]
        return result

    async def _both_channels(self, session, expanded: str,
                             query_vector: list[float]) -> dict[int, HybridHit]:
        """Cosine pass, then best-effort full-text pass, merged by chunk id."""
        # Même élargissement HNSW que RAGService : l'inspecteur reflète
        # exactement le pool que la recherche production verrait.
        await set_hnsw_ef_search(session)
        hits: dict[int, HybridHit] = {}
        rows = (await session.execute(
            cosine_statement(query_vector, self.candidates))).all()
        for chunk, cosine, page_title in rows:
            hits[chunk.id] = self._hit(chunk, page_title,
                                       cosine=cosine, fts=None)
        for lexical in await self._fetch_lexical(
                session, expanded, self.candidates):
            hit = hits.get(lexical.chunk_id)
            if hit is None:
                hits[lexical.chunk_id] = lexical
                continue
            hit.ts_score = lexical.ts_score
            hit.headline = lexical.headline
            hit.score = fuse(hit.cosine_score, hit.ts_score)
        return hits

    async def _fetch_lexical(self, session, query: str,
                             candidates: int) -> list[HybridHit]:
        """PostgreSQL full-text pass (best effort: auxiliary channel).

        An all-stopwords query raises at tsquery parse time; the semantic
        channel still answers, so the failure is swallowed here.
        """
        try:
            rows = (await session.execute(
                fts_statement(query, candidates))).all()
        except Exception:  # noqa: BLE001 — FTS is an auxiliary channel
            return []
        lexical: list[HybridHit] = []
        for chunk, ts, headline, page_title in rows:
            hit = self._hit(chunk, page_title, cosine=None,
                            fts=ts_rank_normalized(ts))
            hit.headline = headline or ""
            lexical.append(hit)
        return lexical

    async def lexical_hits(self, query: str,
                           candidates: int | None = None) -> list[HybridHit]:
        """Lexical channel only (no embedding) — Codex route's BM25 analogue."""
        if not query.strip():
            return []
        async with self.sessions() as session:
            return await self._fetch_lexical(
                session, query, candidates or self.candidates)

    @staticmethod
    def _hit(chunk, page_title: str, *, cosine, fts) -> HybridHit:
        """One hit from a raw row: cleaned content, section, normalized scores."""
        metadata = dict(chunk.chunk_metadata or {})
        hit = HybridHit(
            chunk_id=chunk.id,
            page_title=page_title,
            content=strip_context_prefix(chunk.content_markdown),
            chunk_metadata=metadata,
            section=section_label(metadata),
            cosine_score=cosine if cosine is not None else None,
            ts_score=fts,
            headline="",
        )
        if cosine is not None:
            hit.cosine_score = float(max(0.0, min(1.0, cosine)))
        hit.score = fuse(hit.cosine_score, hit.ts_score)
        return hit


__all__ = ["HybridSearch"]
