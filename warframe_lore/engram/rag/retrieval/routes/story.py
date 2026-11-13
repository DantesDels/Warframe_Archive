"""Route B (Story): pure vector targeting, strict SQL chronology.

A narration is NOT a search result: it must read in the order events happened.
The vector channel only PICKS the semantic neighbourhood (no lexical channel,
no reranker here — both are forbidden on this route); the final order is then
imposed by SQL: dialogue ``message_order`` ascending, page, chunk id.  The
schema has no release date on chunks, so ``message_order`` carries the
chronology.  Non-narrative kinds (patch notes, announcements) are excluded in
SQL, before any row reaches the prompt.
"""

from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from warframe_lore.engram.rag.retrieval.hnsw import (
    HNSW_EF_SEARCH,
    set_hnsw_ef_search,
)
from warframe_lore.engram.rag.retrieval.retriever import (
    STORY_EXCLUDED_KINDS,
    RAGHit,
)
from warframe_lore.storage.db.models import GameDialogue, KimDialogue
from warframe_lore.storage.db.models.structured_chunk import StructuredChunk

STORY_VECTOR_CANDIDATES = 48
STORY_ORDERED_LIMIT = 6


def story_statement(query_vector: list[float], limit: int,
                    *, candidates: int = STORY_VECTOR_CANDIDATES,
                    exclude_ids: list[int] | None = None):
    """Chronological statement over the vector-selected story candidates.

    The CTE is the ONLY semantic step: top ``candidates`` by cosine distance,
    already purged of metagame kinds.  The outer query restores the narrative
    sequence with ``ORDER BY message_order ASC`` — the final order is SQL's,
    never the vector's.
    """
    distance = StructuredChunk.embedding.cosine_distance(query_vector)
    pool = (
        select(StructuredChunk.id.label("chunk_id"))
        .where(
            StructuredChunk.embedding.is_not(None),
            StructuredChunk.kind.notin_(STORY_EXCLUDED_KINDS),
        )
        .order_by(distance)
        .limit(candidates)
        .cte("vector_candidates")
    )
    chronology = func.coalesce(
        KimDialogue.message_order, GameDialogue.message_order)
    stmt = (
        select(StructuredChunk, distance.label("dist"))
        .join(pool, StructuredChunk.id == pool.c.chunk_id)
        .outerjoin(
            KimDialogue,
            and_(StructuredChunk.kind == "kim_dialogues",
                 StructuredChunk.source_id == KimDialogue.id),
        )
        .outerjoin(
            GameDialogue,
            and_(StructuredChunk.kind == "game_dialogues",
                 StructuredChunk.source_id == GameDialogue.id),
        )
        .where(StructuredChunk.kind.notin_(STORY_EXCLUDED_KINDS))
    )
    if exclude_ids:
        stmt = stmt.where(StructuredChunk.id.notin_(exclude_ids))
    return (
        stmt.order_by(
            chronology.asc().nulls_last(),
            StructuredChunk.wiki_page_id.asc(),
            StructuredChunk.id.asc(),
        )
        .limit(limit)
    )


class StoryRoute:
    """Semantic targeting, chronological ordering, no lexical nor rerank."""

    def __init__(self, sessions: async_sessionmaker,
                 limit: int = STORY_ORDERED_LIMIT,
                 candidates: int = STORY_VECTOR_CANDIDATES,
                 ef_search: int = HNSW_EF_SEARCH) -> None:
        self.sessions = sessions
        self.limit = limit
        self.candidates = candidates
        self.ef_search = ef_search

    async def retrieve(self, question: str,
                       query_vector: list[float]) -> list[RAGHit]:
        """The story candidates, already in strict chronological order.

        ``question`` is intentionally unused: scoring the wording would be a
        relevance ranking, which this route forbids.
        """
        statement = story_statement(
            query_vector, self.limit, candidates=self.candidates)
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
                    kind=chunk.kind,
                ))
        return hits


__all__ = ["STORY_ORDERED_LIMIT", "STORY_VECTOR_CANDIDATES", "StoryRoute",
           "story_statement"]
