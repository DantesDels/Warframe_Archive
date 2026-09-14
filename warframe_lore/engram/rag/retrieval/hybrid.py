"""Hybrid search over ``lore_chunks``: pgvector cosine + PostgreSQL FTS.

Backend of the "RAG Inspector" UI. One query is run across the two
retrieval channels and the raw per-channel scores are surfaced for each
chunk, so an operator can audit what a RAG call would ground on:

    * semantic channel — cosine distance on the query embedding
      (pgvector ``<=>``); the query is pre-expanded by the alias
      middleware (nickname -> canonical name), like ``RAGService.retrieve``;
    * lexical channel   — PostgreSQL full-text (``websearch_to_tsquery``,
      ``ts_rank_cd`` + ``ts_headline``) on the ``french`` configuration.

Every hit exposes its ``chunk_metadata`` (JSONB: heading hierarchy /
section / speakers) and both scores. The single ``score`` field is only a
transparent fusion used for ordering — never hidden from the inspector.

Channels are intentionally NOT fused in SQL: each one keeps its own
retrieval (HNSW ordering for cosine, ``ts_rank`` for FTS) and the hits are
merged and ranked in Python.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ....db import LoreChunk, WikiPage
from ...llm import EmbeddingProvider
from ..query.aliases import AliasResolver
from .search import set_hnsw_ef_search

# ts_headline output cap (PostgreSQL options string — no inner quotes).
_FTS_HEADLINE_OPTIONS = "MaxWords=40, MinWords=15, MaxFragments=2"

# Fusion weights: cosine is the primary signal, full-text the lexical guard.
_COSINE_WEIGHT = 0.6
_FTS_WEIGHT = 0.4

# French lexical configuration used by the FTS channel.
_FTS_CONFIG = "french"

_WORD = re.compile(r"[^\W\d_][\w'-]*", re.UNICODE)

# Context prefix injected at ingestion time ("Page: X | Section: Y - ..."):
# stripped from the served content, the header [page] > [section] already
# carries that context.
_CONTEXT_PREFIX = re.compile(r"^Page: [^\n]+?(?: \| Section: [^\n]*?)? - ")


def query_terms(query: str) -> list[str]:
    """Exact, deduplicated, ordered terms of the query (for highlighting).

    Keeps the raw user wording (the "exact terms" visible in the corpus)
    rather than the stemmed lexemes: matching stays faithful to the text.
    """
    seen: set[str] = set()
    terms: list[str] = []
    for token in _WORD.findall(query.casefold()):
        if len(token) >= 3 and token not in seen:
            seen.add(token)
            terms.append(token)
    return terms


def _section_label(metadata: dict[str, Any]) -> str:
    """Section chain of a chunk: ``metadata["section"]`` or the heading
    hierarchy (``Header 2``.. ``Header 6``), skipping the page-level ``h1``."""
    section = metadata.get("section")
    if section:
        return str(section)
    titles = [str(metadata[f"Header {level}"])
              for level in range(2, 7)
              if metadata.get(f"Header {level}")]
    return " > ".join(title for title in titles if title)


def strip_context_prefix(content: str) -> str:
    """Drops the ingestion-time ``Page: X | Section: Y - `` prefix."""
    return _CONTEXT_PREFIX.sub("", content, count=1).strip()


def ts_rank_normalized(ts_rank: float) -> float:
    """Maps ``ts_rank_cd`` (unbounded) frequency to 0..1 (r/(1+r))."""
    if ts_rank is None or ts_rank < 0:
        return 0.0
    return ts_rank / (1.0 + ts_rank)


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
        return bool(self.alias_note)


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

    # ------------------------------------------------------------------ SQL
    def _cosine_statement(self, query_vector: list[float]):
        """Top candidates by cosine similarity (no hard floor: the inspector
        must see weak hits too, thresholds belong to RAGService)."""
        distance = LoreChunk.embedding.cosine_distance(query_vector)
        return (
            select(LoreChunk,
                   (1.0 - distance).label("cos"),
                   WikiPage.page_title)
            .join(WikiPage, LoreChunk.wiki_page_id == WikiPage.page_id)
            .where(LoreChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(self.candidates)
        )

    def _fts_statement(self, query: str):
        """Top candidates by French full-text rank (+ matching snippet)."""
        tsvector = func.to_tsvector(_FTS_CONFIG, LoreChunk.content_markdown)
        tsquery = func.websearch_to_tsquery(_FTS_CONFIG, query)
        return (
            select(LoreChunk,
                   func.ts_rank_cd(tsvector, tsquery, 32).label("ts"),
                   func.ts_headline(_FTS_CONFIG, LoreChunk.content_markdown,
                                    tsquery, _FTS_HEADLINE_OPTIONS)
                   .label("headline"),
                   WikiPage.page_title)
            .join(WikiPage, LoreChunk.wiki_page_id == WikiPage.page_id)
            .where(tsvector.op("@@")(tsquery))
            .order_by(func.ts_rank_cd(tsvector, tsquery, 32).desc())
            .limit(self.candidates)
        )

    # ------------------------------------------------------------------ run
    async def search(self, question: str, limit: int = 12) -> HybridQuery:
        """Resolves aliases, embeds the expanded query, retrieves both
        channels and returns the fused, ranked hits."""
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
            hits: dict[int, HybridHit] = {}
            # Même élargissement HNSW que RAGService : l'inspecteur reflète
            # exactement le pool que la recherche production verrait.
            await set_hnsw_ef_search(session)

            cosine_rows = (await session.execute(
                self._cosine_statement(query_vector))).all()
            for chunk, cos, page_title in cosine_rows:
                hits[chunk.id] = self._hit(chunk, page_title,
                                           cosine=cos, fts=None)

            # Full-text pass is best-effort: an all-stopwords query raises at
            # tsquery parse time — the semantic channel still answers.
            try:
                fts_rows = (await session.execute(
                    self._fts_statement(expanded))).all()
            except Exception:  # noqa: BLE001 — FTS is an auxiliary channel
                fts_rows = []

            for chunk, ts, headline, page_title in fts_rows:
                hit = hits.get(chunk.id)
                if hit is None:
                    hit = self._hit(chunk, page_title,
                                    cosine=None, fts=ts_rank_normalized(ts))
                    hits[chunk.id] = hit
                else:
                    hit.ts_score = ts_rank_normalized(ts)
                    hit.headline = headline or ""
                    hit.score = self._fuse(hit.cosine_score, hit.ts_score)

        result.hits = sorted(hits.values(), key=lambda h: h.score,
                             reverse=True)[:max(limit, 1)]
        return result

    # --------------------------------------------------------------- helpers
    def _hit(self, chunk, page_title, *, cosine, fts):
        metadata = dict(chunk.chunk_metadata or {})
        hit = HybridHit(
            chunk_id=chunk.id,
            page_title=page_title,
            content=strip_context_prefix(chunk.content_markdown),
            chunk_metadata=metadata,
            section=_section_label(metadata),
            cosine_score=cosine if cosine is not None else None,
            ts_score=fts,
            headline="",
        )
        if cosine is not None:
            hit.cosine_score = float(max(0.0, min(1.0, cosine)))
        hit.score = self._fuse(hit.cosine_score, hit.ts_score)
        return hit

    @staticmethod
    def _fuse(cosine: float | None, ts: float | None) -> float:
        """Weighted fusion of the normalized per-channel scores."""
        if cosine is not None and ts is not None:
            return _COSINE_WEIGHT * cosine + _FTS_WEIGHT * ts
        if cosine is not None:
            return _COSINE_WEIGHT * cosine
        if ts is not None:
            return _FTS_WEIGHT * ts
        return 0.0


__all__ = ["HybridHit", "HybridQuery", "HybridSearch", "query_terms",
           "strip_context_prefix", "ts_rank_normalized"]
