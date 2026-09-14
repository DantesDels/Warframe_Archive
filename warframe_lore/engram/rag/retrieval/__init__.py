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
    "HybridHit": ".hybrid",
    "HybridQuery": ".hybrid",
    "HybridSearch": ".hybrid",
    "RAGHit": ".retriever",
    "Retriever": ".retriever",
    "query_terms": ".hybrid",
    "set_hnsw_ef_search": ".search",
    "strip_context_prefix": ".hybrid",
    "ts_rank_normalized": ".hybrid",
}

install(sys.modules[__name__], _EXPORTS)
