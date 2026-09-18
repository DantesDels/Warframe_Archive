"""Vector search on ``structured_chunks`` (human-readable element tables).

Mirrors :class:`CosinusSearch` (``lore_chunks``) but targets the structured
corpus.  The ``MergedRetriever`` composes both channels.
"""

from __future__ import annotations

import os

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ....db import WikiPage
from ....db.models import GameDialogue, KimDialogue
from ....db.models.structured_chunk import StructuredChunk
from ....protocols.roleplay import STORY_DOSSIER_PAGE
from .retriever import DossierPage, RAGHit, Retriever
from .search import set_hnsw_ef_search

HNSW_EF = int(os.getenv("ENGRAM_HNSW_EF", "200"))


class StructuredSearch(Retriever):
    """Queries ``structured_chunks`` by cosine similarity."""

    def __init__(
        self, sessions: async_sessionmaker, top_k: int = 6, ef_search: int = HNSW_EF
    ) -> None:
        self.sessions = sessions
        self.top_k = top_k
        self.ef_search = ef_search

    async def search(self, query_vector: list[float]) -> list[RAGHit]:
        """Top ``top_k`` structured rows closest to the query vector."""
        distance = StructuredChunk.embedding.cosine_distance(
            query_vector).label("dist")
        stmt = (
            select(StructuredChunk, distance)
            .where(StructuredChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(self.top_k)
        )
        hits: list[RAGHit] = []
        async with self.sessions() as session:
            await set_hnsw_ef_search(session, self.ef_search)
            rows = (await session.execute(stmt)).all()
            for chunk, dist in rows:
                hits.append(RAGHit(
                    chunk_id=chunk.id,
                    page_title=chunk.title,
                    content=chunk.content,
                    score=1.0 - float(dist),
                ))
        return hits

    def _build_dossier_statement(self, subject: str,
                                 query_vector: list[float],
                                 limit: int = STORY_DOSSIER_PAGE,
                                 offset: int = 0,
                                 exclude_ids: list[int] | None = None):
        """SELECT statement: subject-title structured rows, story-first.

        Same tier shape as the lore dossier (exact title, French mirror,
        sections, everything else) but the narrative order comes from the
        dialogue tables: after the page join, ``message_order`` restores the
        in-conversation sequence of ``kim_dialogues`` / ``game_dialogues`` rows
        (``id`` breaks the tie for the other kinds).  ``exclude_ids`` bans the
        already-narrated chunks — the only cursor the server trusts.
        """
        distance = StructuredChunk.embedding.cosine_distance(
            query_vector).label("dist")
        tier = case(
            (StructuredChunk.title.ilike(subject), 0),
            (StructuredChunk.title.ilike(f"{subject} (fr)"), 0),
            (StructuredChunk.title.ilike(f"{subject}/%"), 1),
            else_=2,
        )
        # No ORM relationship on StructuredChunk: explicit joins only, plus
        # outerjoins so non-dialogue kinds keep their ``message_order`` NULL.
        stmt = (
            select(StructuredChunk, distance)
            .join(WikiPage, StructuredChunk.wiki_page_id == WikiPage.page_id)
            .outerjoin(
                KimDialogue,
                (StructuredChunk.kind == "kim_dialogues")
                & (StructuredChunk.source_id == KimDialogue.id),
            )
            .outerjoin(
                GameDialogue,
                (StructuredChunk.kind == "game_dialogues")
                & (StructuredChunk.source_id == GameDialogue.id),
            )
            .where(
                StructuredChunk.embedding.is_not(None),
                WikiPage.page_title.ilike(f"%{subject}%"),
            )
        )

        # Exclusion filter: the chunks the session already narrated.
        if exclude_ids:
            stmt = stmt.where(StructuredChunk.id.notin_(exclude_ids))

        # Reading order: dialogue sequence first, chunk id as tie-breaker.
        return (
            stmt.order_by(
                tier,
                KimDialogue.message_order.asc().nulls_last(),
                GameDialogue.message_order.asc().nulls_last(),
                StructuredChunk.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )

    async def dossier(self, subject: str, query_vector: list[float],
                      limit: int = STORY_DOSSIER_PAGE,
                      offset: int = 0,
                      exclude_ids: list[int] | None = None) -> DossierPage:
        """One page of the subject's structured dossier, story-first.

        ``offset`` is a continuation marker kept for the wire contract (the
        pipeline always pages from ``0``); ``exclude_ids`` is the real cursor.
        One row is fetched beyond the window to know whether anything remains.
        """
        statement = self._build_dossier_statement(
            subject, query_vector, limit + 1, offset, exclude_ids)
        hits: list[RAGHit] = []
        async with self.sessions() as session:
            await set_hnsw_ef_search(session, self.ef_search)
            rows = (await session.execute(statement)).all()
            for chunk, dist in rows:
                hits.append(RAGHit(
                    chunk_id=chunk.id,
                    page_title=chunk.title,
                    content=chunk.content,
                    score=1.0 - float(dist),
                ))
        return DossierPage(hits=hits[:limit], more=len(hits) > limit)


__all__ = ["HNSW_EF", "StructuredSearch"]
