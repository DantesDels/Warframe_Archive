"""Document RAG: vector retrieval, prompt and orchestration.

    * ``retriever`` -> :class:`RAGHit` + :class:`Retriever` (contract);
    * ``search``    -> :class:`CosinusSearch` (pgvector implementation);
    * ``prompt``    -> :class:`PromptBuilder` / :class:`RAGPrompt`;
    * ``service``   -> :class:`RAGService` (orchestration, depends on
      abstractions; ephemeral per-request memory via :class:`RAGContext`);
    * ``aliases``   -> :class:`AliasResolver` (nickname -> canonical name,
      applied to the raw query before vectorization);
    * ``sanitize``  -> :func:`strip_trailing_padding` (output artifacts).
"""

from __future__ import annotations

from .aliases import AliasResolver
from .context import RAGContext, RAGContextFactory
from .prompt import (JAILBREAK_REJECT, NO_DATA_MARKER, OFF_TOPIC_ERROR,
                     PromptBuilder, RAGPrompt, RAG_ERROR)
from .retriever import RAGHit, Retriever
from .rewriter import QueryRewriter
from .sanitize import strip_trailing_padding
from .search import CosinusSearch
from .service import RAGService

__all__ = ["AliasResolver", "JAILBREAK_REJECT", "RAG_ERROR", "OFF_TOPIC_ERROR",
           "CosinusSearch", "PromptBuilder", "QueryRewriter",
           "RAGContext", "RAGContextFactory", "RAGHit", "RAGPrompt",
           "RAGService", "Retriever", "strip_trailing_padding"]