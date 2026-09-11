"""Vector search by cosine similarity on ``lore_chunks``.

Implementation of :class:`Retriever` (PostgreSQL/pgvector): uses the
``<=>`` operator (cosine distance) via the :class:`LoreChunk` ORM.
Lowest distance = closest passage; exposed as similarity
(1 - distance). The retriever owns its own ``async_sessionmaker``.
"""

from __future__ import annotations

import difflib
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from ...db import LoreChunk, WikiPage
from .retriever import RAGHit, Retriever

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
        if word and difflib.SequenceMatcher(None, token, word).ratio() >= _TOKEN_WORD_RATIO:
            return True
    return False


class CosinusSearch(Retriever):
    """Queries ``lore_chunks`` by cosine similarity of the query vector."""

    def __init__(self, sessions: async_sessionmaker,
                 top_k: int = 6, min_score: float = 0.35) -> None:
        self.sessions = sessions
        self.top_k = top_k
        self.min_score = min_score

    def _build_statement(self, query_vector: list[float]):
        """SELECT statement enforcing ``min_score`` in SQL (max distance)."""
        distance = LoreChunk.embedding.cosine_distance(
            query_vector).label("dist")
        return (
            select(LoreChunk, distance)
            .options(selectinload(LoreChunk.wiki_page))
            .where(LoreChunk.embedding.is_not(None))
            .where(distance <= (1.0 - self.min_score))
            .order_by(distance)
            .limit(self.top_k)
        )

    async def search(self, query_vector: list[float]) -> list[RAGHit]:
        """Returns passages closest to ``query_vector``.

        The SQL query enforces ``min_score`` directly in the WHERE clause
        (``distance <= 1 - min_score``), so pgvector never returns
        off-topic chunks.  Chunks below threshold are rejected at the
        database level before any Python post-processing.
        """
        statement = self._build_statement(query_vector)
        hits: list[RAGHit] = []
        async with self.sessions() as session:
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