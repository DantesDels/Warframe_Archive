"""Recherche documentaire : contrat, pgvector, hybride vectoriel + plein texte.

Façade PARESSEUSE du sous-paquet (voir :mod:`warframe_lore.lazy_facade`) :
:mod:`retriever` (contrat ``Retriever`` + ``RAGHit``, sans dépendance),
:mod:`search` (cosinus pgvector) et :mod:`hybrid` (fusion vectoriel + FTS de
l'inspector).  ``retriever`` reste ainsi importable sans SQLAlchemy.
"""

from __future__ import annotations

import sys

from warframe_lore.lazy_facade import install

_EXPORTS = {
    "CODEX_LEXICAL_CANDIDATES": ".routes.codex",
    "CODEX_TOP_N": ".routes.codex",
    "CodexRoute": ".routes.codex",
    "CosinusSearch": ".search",
    "DossierPage": ".retriever",
    "HybridHit": ".model",
    "HybridQuery": ".model",
    "HybridSearch": ".hybrid",
    "LexicalChannel": ".routes.codex",
    "MergedRetriever": ".merged",
    "RAGHit": ".retriever",
    "Reranker": ".routes.rerank",
    "RetrievalIntent": ".routes.intent",
    "RetrievalRouter": ".routes.router",
    "Retriever": ".retriever",
    "STORY_ORDERED_LIMIT": ".routes.story",
    "STORY_VECTOR_CANDIDATES": ".routes.story",
    "SimulatedCrossEncoderReranker": ".routes.rerank",
    "StoryRoute": ".routes.story",
    "StructuredSearch": ".structured_search",
    "classify_intent": ".routes.intent",
    "dedupe_first": ".hits",
    "query_terms": ".scoring",
    "set_hnsw_ef_search": ".search",
    "story_statement": ".routes.story",
    "strip_context_prefix": ".scoring",
    "ts_rank_normalized": ".scoring",
}

install(sys.modules[__name__], _EXPORTS)
