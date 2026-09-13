"""Vector search by cosine similarity on ``lore_chunks``.

Implementation of :class:`Retriever` (PostgreSQL/pgvector): uses the
``<=>`` operator (cosine distance) via the :class:`LoreChunk` ORM.
Lowest distance = closest passage; exposed as similarity
(1 - distance). The retriever owns its own ``async_sessionmaker``.
"""

from __future__ import annotations

import difflib
import os
import re

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from ...db import LoreChunk, WikiPage
from .retriever import RAGHit, Retriever

# HNSW recall: the index scans ef_search candidates per probe (default 40).
# On a large corpus (~1000+ pages x ~30 chunks) with top_k=3 the default is
# too tight — the pool is widened here, per query (session GUC, COST: 40).
HNSW_EF_SEARCH = int(os.getenv("ENGRAM_HNSW_EF", "200"))

# French stopwords deemed non-discriminant for title search.
_STOPWORDS = {
    "qu'est", "c'est", "comment", "pourquoi", "combien", "histoire",
    "parle", "dis", "decrit", "decris", "raconte", "connais", "sais",
    "dans", "avec", "dont", "comme", "mais", "sont", "est", "et",
    "les", "des", "une", "que", "qui", "pas", "vous",
}

_ALNUM = re.compile(r"[a-zA-Z0-9'_-]+")

# Minimal title token/word ratio for disambiguation: STRICT (0.93) to
# only propose real near-matches of proper names. Without it,
# "une souris verte" → token "verte" validates the title "Aurax Vertec"
# (misleading substring) and Oracle suggests an unrelated entity.
_TOKEN_WORD_RATIO = 0.93


def _token_matches_title(token: str, title: str) -> bool:
    """The token is lexically close to a WORD of the title (not just a
    substring inside a longer word)."""
    for word in _ALNUM.findall(title.lower()):
        if word and difflib.SequenceMatcher(
                None, token, word).ratio() >= _TOKEN_WORD_RATIO:
            return True
    return False


async def set_hnsw_ef_search(session, ef: int = HNSW_EF_SEARCH) -> None:
    """Widens the pgvector HNSW scan pool for the CURRENT transaction.

    ``hnsw.ef_search`` is the index parameter that caps how many candidates
    are scanned per probe (default 40).  Raised here per query so a growing
    corpus keeps its recall without rebuilding the index.
    """
    # Inlined integer (safe: int cast — no interpolation of user input).
    await session.execute(text(f"SET LOCAL hnsw.ef_search = {int(ef)}"))


class CosinusSearch(Retriever):
    """Queries ``lore_chunks`` by cosine similarity of the query vector."""

    def __init__(self, sessions: async_sessionmaker,
                 top_k: int = 6, min_score: float = 0.35,
                 ef_search: int = HNSW_EF_SEARCH) -> None:
        self.sessions = sessions
        self.top_k = top_k
        # DEPRECATED: kept for backward compatibility only.  Relevance is
        # decided in ONE place, RAGService.retrieve (``min_score`` config).
        # The SQL layer returns a candidate pool WITHOUT a semantic floor, so
        # the suggestion/disambiguation path sees weak hits too (single
        # threshold — before, SQL ``WHERE`` + Python ``floor`` could disagree).
        self.min_score = min_score
        self.ef_search = ef_search

    def _build_statement(self, query_vector: list[float]):
        """SELECT statement: top ``top_k`` candidates by cosine distance.

        No relevance floor here: pgvector returns the top_k closest chunks and
        re-ranking + thresholding happens EXACTLY ONCE in
        :meth:`RAGService.retrieve` (``suggestion_min_score`` /
        ``critical_min_score``).  A WHERE on distance AND a Python floor were
        the double-threshold bug: two places could disagree and the SQL floor
        silently starved the suggestion path.
        """
        distance = LoreChunk.embedding.cosine_distance(
            query_vector).label("dist")
        return (
            select(LoreChunk, distance)
            .options(selectinload(LoreChunk.wiki_page))
            .where(LoreChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(self.top_k)
        )

    async def search(self, query_vector: list[float]) -> list[RAGHit]:
        """Returns the ``top_k`` passages closest to ``query_vector``.

        The candidate pool is bounded in SQL (``LIMIT top_k``); the semantic
        threshold lives exclusively in ``RAGService`` — one source of truth.
        """
        statement = self._build_statement(query_vector)
        hits: list[RAGHit] = []
        async with self.sessions() as session:
            await set_hnsw_ef_search(session, self.ef_search)
            rows = (await session.execute(statement)).all()
            for chunk, dist in rows:
                score = 1.0 - float(dist)
                hits.append(RAGHit(
                    chunk_id=chunk.id,
                    page_title=chunk.wiki_page.page_title,
                    content=chunk.content_markdown,
                    score=score,
                ))
        return hits

    async def suggest_title(self, question: str) -> str | None:
        """Page title where a question token is a substring.

        Lexical fallback: tokens are tested from longest to shortest — the
        most specific word is the most discriminant — and the first title
        found in ``wiki_pages`` is returned, or None.
        """
        tokens = {t for t in _ALNUM.findall(question.lower())
                  if len(t) >= 3 and t not in _STOPWORDS}
        async with self.sessions() as session:
            for token in sorted(tokens, key=len, reverse=True):
                title = (await session.execute(
                    select(WikiPage.page_title)
                    .where(WikiPage.page_title.ilike(f"%{token}%"))
                    .limit(1))).scalar_one_or_none()
                if title and _token_matches_title(token, title):
                    return title
        return None
