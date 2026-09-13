"""Document RAG: vector retrieval, prompt and orchestration.

    * ``retriever``    -> :class:`RAGHit` + :class:`Retriever` (contract);
    * ``search``       -> :class:`CosinusSearch` (pgvector implementation);
    * ``prompt``       -> :class:`PromptBuilder` / :class:`RAGPrompt`;
    * ``guards``       -> shared security/guard chains;
    * ``query_guard``  -> query sanitisation + entity-lookup guard;
    * ``service``      -> :class:`RAGService` (orchestration, depends on
      abstractions; ephemeral per-request memory via :class:`RAGContext`);
    * ``aliases``      -> :class:`AliasResolver` (nickname -> canonical name,
      applied to the raw query before vectorization);
    * ``sanitize``     -> :func:`strip_trailing_padding` (output artifacts).
"""

from __future__ import annotations

from .aliases import AliasResolver
from .context import RAGContext, RAGContextFactory
from .guards import JAILBREAK_REJECT, OFF_TOPIC_ERROR, RAG_ERROR
from .hybrid import (
                     HybridHit,
                     HybridQuery,
                     HybridSearch,
                     query_terms,
                     strip_context_prefix,
                     ts_rank_normalized,
)
from .prompt import NO_DATA_MARKER, PromptBuilder, RAGPrompt
from .retriever import RAGHit, Retriever
from .rewriter import QueryRewriter
from .sanitize import strip_trailing_padding
from .search import CosinusSearch
from .service import RAGService

__all__ = ["AliasResolver", "JAILBREAK_REJECT", "RAG_ERROR", "OFF_TOPIC_ERROR",
           "CosinusSearch", "HybridHit", "HybridQuery", "HybridSearch",
           "NO_DATA_MARKER", "PromptBuilder", "QueryRewriter", "query_terms",
           "RAGContext", "RAGContextFactory", "RAGHit", "RAGPrompt",
           "RAGService", "Retriever", "strip_context_prefix",
           "strip_trailing_padding", "ts_rank_normalized"]
