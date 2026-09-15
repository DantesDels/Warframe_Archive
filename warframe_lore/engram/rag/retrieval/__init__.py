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
    "CosinusSearch": ".search",
    "HybridHit": ".model",
    "HybridQuery": ".model",
    "HybridSearch": ".hybrid",
    "MergedRetriever": ".merged",
    "RAGHit": ".retriever",
    "Retriever": ".retriever",
    "StructuredSearch": ".structured_search",
    "query_terms": ".scoring",
    "set_hnsw_ef_search": ".search",
    "strip_context_prefix": ".scoring",
    "ts_rank_normalized": ".scoring",
}

install(sys.modules[__name__], _EXPORTS)
