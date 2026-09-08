"""Recherche vectorielle par similarité cosinus sur ``lore_chunks``.

Implémentation de :class:`Retriever` (PostgreSQL/pgvector) : utilise
l'opérateur ``<=>`` (distance cosinus) via l'ORM :class:`LoreChunk`.
Distance la plus faible = passage le plus proche ; exposé en similarité
(1 - distance).  Le retriever possède son propre ``async_sessionmaker``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from ...db import LoreChunk
from .retriever import RAGHit, Retriever


class CosinusSearch(Retriever):
    """Interroge ``lore_chunks`` par similarité cosinus du vecteur de requête."""

    def __init__(self, sessions: async_sessionmaker,
                 top_k: int = 6, min_score: float = 0.35) -> None:
        self.sessions = sessions
        self.top_k = top_k
        self.min_score = min_score

    async def search(self, query_vector: list[float]) -> list[RAGHit]:
        """Retourne les passages les plus proches de ``query_vector``."""
        distance = LoreChunk.embedding.cosine_distance(query_vector).label("dist")
        statement = (
            select(LoreChunk, distance)
            .options(selectinload(LoreChunk.wiki_page))
            .where(LoreChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(self.top_k)
        )
        hits: list[RAGHit] = []
        async with self.sessions() as session:
            rows = (await session.execute(statement)).all()
            for chunk, dist in rows:
                score = 1.0 - float(dist)
                if score < self.min_score:
                    continue
                hits.append(RAGHit(
                    chunk_id=chunk.id,
                    page_title=chunk.wiki_page.page_title,
                    content=chunk.content_markdown,
                    score=score,
                ))
        return hits