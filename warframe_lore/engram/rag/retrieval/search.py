"""Vector search by cosine similarity on ``lore_chunks``.

Implementation of :class:`Retriever` (PostgreSQL/pgvector): uses the
``<=>`` operator (cosine distance) via the :class:`LoreChunk` ORM.
Lowest distance = closest passage; exposed as similarity
(1 - distance). The retriever owns its own ``async_sessionmaker``.

Facade of the lore-channel retrieval: the cosine search itself (this
module), the subject dossier (:mod:`.dossier`), the lexical title
suggestion (:mod:`.suggestion`) and the HNSW session tuning
(:mod:`.hnsw`).  The helper names shared by the other retrieval channels
(``set_hnsw_ef_search``, ``dossier_title_terms``, ``DOSSIER_LIMIT``,
``_token_matches_title``) are re-exported here to keep the public API
stable.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from ....db import LoreChunk
from ..query.aliases import dossier_title_terms
from .dossier import DOSSIER_LIMIT, fetch_dossier_page, lore_dossier_statement
from .hnsw import HNSW_EF_SEARCH, set_hnsw_ef_search
from .retriever import DossierPage, RAGHit, Retriever
from .suggestion import _token_matches_title, suggest_page_title


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

    def _build_dossier_statement(self, subject: str,
                                 query_vector: list[float],
                                 limit: int = DOSSIER_LIMIT,
                                 offset: int = 0,
                                 exclude_ids: list[int] | None = None):
        """SELECT statement: subject chunks in narrative reading order.

        Story-first dossier tiers (exact biography page, its sections, title
        matches, content-only mentions).  The SQL lives in
        :func:`lore_dossier_statement`; this method keeps the public shape of
        the retriever so the RAG pipeline and the tests call one entry point.
        """
        return lore_dossier_statement(
            subject, query_vector, limit, offset, exclude_ids)

    async def dossier(self, subject: str, query_vector: list[float],
                      limit: int = DOSSIER_LIMIT,
                      offset: int = 0,
                      exclude_ids: list[int] | None = None) -> DossierPage:
        """One page of the subject's dossier, story-first.

        Targeted-story anchoring (playtest "l'histoire d'Eleanor"): the pure
        semantic search ranks first-person KIM dialogues above the subject's
        narrative page — the Eleanor Background section landed at rank ~16,
        far under the top_k=3, so the story corpus carried no actual story.
        This dossier walks the subject's OWN pages in READING order — the
        exact biography page (``Eleanor``, or ``Leticia`` when the key is the
        alias ``lettie``) first, then its section pages (``Eleanor/Quotes``),
        then TITLE-matching pages, then content-only mentions — so a targeted
        story is grounded on the narrative itself.  Each chunk keeps its
        cosine score: the relevance floor still drops off-story sections.
        ``offset`` is a continuation marker kept for the wire contract (the
        pipeline always pages from ``0``); ``exclude_ids`` is the real cursor:
        the chunks the session already narrated are banned in SQL.  One chunk
        is fetched beyond the window to know whether anything is left (no
        COUNT query).  Executed by :func:`fetch_dossier_page`.
        """
        return await fetch_dossier_page(
            self.sessions, self.ef_search, subject, query_vector,
            limit, offset, exclude_ids)

    async def suggest_title(self, question: str) -> str | None:
        """Page title where a question token is a substring.

        Lexical fallback: tokens are tested from longest to shortest — the
        most specific word is the most discriminant — and the first title
        found in ``wiki_pages`` is returned, or None.  Runs
        :func:`suggest_page_title` on this retriever's session maker.
        """
        return await suggest_page_title(self.sessions, question)


__all__ = ["CosinusSearch", "DOSSIER_LIMIT", "HNSW_EF_SEARCH",
           "_token_matches_title", "dossier_title_terms",
           "lore_dossier_statement", "set_hnsw_ef_search"]
