"""Recherche documentaire : contrat, pgvector, hybride vectoriel + plein texte.

Façade du sous-paquet : :mod:`retriever` (contrat ``Retriever`` + ``RAGHit``),
:mod:`search` (cosinus pgvector), :mod:`hybrid` (fusion vectoriel + FTS pour
l'inspector).  Les noms publics restent importables depuis
``warframe_lore.engram.rag``.
"""

from __future__ import annotations

from .hybrid import (
    HybridHit,
    HybridQuery,
    HybridSearch,
    query_terms,
    strip_context_prefix,
    ts_rank_normalized,
)
from .retriever import RAGHit, Retriever
from .search import CosinusSearch, set_hnsw_ef_search

__all__ = ["CosinusSearch", "HybridHit", "HybridQuery", "HybridSearch",
           "RAGHit", "Retriever", "query_terms", "set_hnsw_ef_search",
           "strip_context_prefix", "ts_rank_normalized"]
