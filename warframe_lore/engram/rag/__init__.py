"""Document RAG: vector retrieval, prompt and orchestration.

    * ``retriever`` -> :class:`RAGHit` + :class:`Retriever` (contract);
    * ``search``    -> :class:`CosinusSearch` (pgvector implementation);
    * ``prompt``    -> :class:`PromptBuilder` / :class:`RAGPrompt`;
    * ``service``   -> :class:`RAGService` (orchestration, depends on abstractions).
"""

from __future__ import annotations

from .prompt import (JAILBREAK_REJECT, NO_DATA_MARKER, PromptBuilder,
                     RAGPrompt, RAG_ERROR)
from .retriever import RAGHit, Retriever
from .rewriter import QueryRewriter
from .search import CosinusSearch
from .service import RAGService

__all__ = ["JAILBREAK_REJECT", "RAG_ERROR", "CosinusSearch", "PromptBuilder",
           "QueryRewriter", "RAGHit", "RAGPrompt", "RAGService", "Retriever"]