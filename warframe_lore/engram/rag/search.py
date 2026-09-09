"""Recherche vectorielle par similarité cosinus sur ``lore_chunks``.

Implémentation de :class:`Retriever` (PostgreSQL/pgvector) : utilise
l'opérateur ``<=>`` (distance cosinus) via l'ORM :class:`LoreChunk`.
Distance la plus faible = passage le plus proche ; exposé en similarité
(1 - distance).  Le retriever possède son propre ``async_sessionmaker``.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from ...db import LoreChunk, WikiPage
from .retriever import RAGHit, Retriever

# Mots-outils français jugés non discriminant pour la recherche de titres.
_STOPWORDS = {
    "qu'est", "c'est", "comment", "pourquoi", "combien", "histoire",
    "parle", "dis", "decrit", "decris", "raconte", "connais", "sais",
    "dans", "avec", "dont", "comme", "mais", "sont", "est", "et",
    "les", "des", "une", "que", "qui", "pas", "vous",
}

_ALNUM = re.compile(r"[a-zA-Z0-9'_-]+")


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

    async def suggest_title(self, question: str) -> str | None:
        """Titre de page dont un token de la question est une sous-chaîne.

        Repli lexical : on teste les tokens du plus long au plus court — le
        mot le plus spécifique est le plus discriminant — et on retourne le
        premier titre trouvé dans ``wiki_pages``, ou None.
        """
        tokens = {t for t in _ALNUM.findall(question.lower())
                  if len(t) >= 3 and t not in _STOPWORDS}
        async with self.sessions() as session:
            for token in sorted(tokens, key=len, reverse=True):
                title = (await session.execute(
                    select(WikiPage.page_title)
                    .where(WikiPage.page_title.ilike(f"%{token}%"))
                    .limit(1))).scalar_one_or_none()
                if title:
                    return title
        return None