"""RAG documentaire : récupération vectorielle, prompt et orchestration.

    * ``retriever``-> :class:`RAGHit` + :class:`Retriever` (contrat) ;
    * ``search``   -> :class:`CosinusSearch` (implémentation pgvector) ;
    * ``prompt``   -> :class:`PromptBuilder` / :class:`RAGPrompt` ;
    * ``service``  -> :class:`RAGService` (orchestration, dépend des abstraits).
"""

from __future__ import annotations

from .prompt import (JAILBREAK_REJECT, NO_DATA_MARKER, PromptBuilder,
                     RAGPrompt, RAG_ERROR)
from .retriever import RAGHit, Retriever
from .search import CosinusSearch
from .service import RAGService

__all__ = ["JAILBREAK_REJECT", "RAG_ERROR", "CosinusSearch", "PromptBuilder",
           "RAGHit", "RAGPrompt", "RAGService", "Retriever"]