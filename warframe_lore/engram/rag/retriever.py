"""Contrat d'accès au corpus vectoriel pour le moteur RAG.

Abstraction (``typing.Protocol``) : ``RAGService`` dépend de cette interface,
jamais d'un stockage concret.  ``CosinusSearch`` (PostgreSQL/pgvector) en est
une implémentation ; on peut en brancher d'autres (FAISS, Qdrant… ) par simple
substitution — sans altérer le cœur du moteur (principes O, D, L).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class RAGHit:
    """Un passage pertinent trouvé par la recherche vectorielle."""

    chunk_id: int
    page_title: str
    content: str
    score: float  # similarité cosinus (1 - distance)


@runtime_checkable
class Retriever(Protocol):
    """Recherche les passages les plus proches d'un vecteur de requête."""

    async def search(self, query_vector: list[float]) -> list[RAGHit]:
        """Retourne les passages pertinents (limités + seuil de score)."""

    async def suggest_title(self, question: str) -> str | None:
        """Titre de page proche lexiquement de la question, ou None.

        Repli de désambiguïsation : utilisé uniquement quand la recherche
        vectorielle ne remonte aucun passage pour la requête demandée.
        """


__all__ = ["RAGHit", "Retriever"]