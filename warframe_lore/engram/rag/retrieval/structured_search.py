"""Vector search on ``structured_chunks`` (human-readable element tables).

Mirrors :class:`CosinusSearch` (``lore_chunks``) but targets the structured
corpus.  The ``MergedRetriever`` composes both channels.
"""

from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ....db.models.structured_chunk import StructuredChunk
from .retriever import RAGHit, Retriever
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
        distance = StructuredChunk.embedding.cosine_distance(query_vector).label("dist")
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
                hits.append(
                    RAGHit(
                        chunk_id=chunk.id,
                        page_title=chunk.title,
                        content=chunk.content,
                        score=1.0 - float(dist),
                    )
                )
        return hits
