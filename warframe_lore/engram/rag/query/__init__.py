"""Analyse de la requête entrante.

Façade PARESSEUSE du sous-paquet (voir :mod:`warframe_lore.lazy_facade`) :
sonde hostile et détecteurs de questions (:mod:`probes`), sanitisation et garde
d'entité (:mod:`query_guard`), aliases mnémoniques (:mod:`aliases`), réécriture
de requête (:mod:`rewriter`, seul module à charger un provider LLM).
"""

from __future__ import annotations

import sys

from warframe_lore.lazy_facade import install

_EXPORTS = {
    "ALIASES": ".aliases",
    "AliasResolver": ".aliases",
    "QueryRewriter": ".rewriter",
    "detect_probe": ".probes",
    "is_identity_question": ".probes",
    "is_self_reflection": ".probes",
    "resolve_alias": ".aliases",
    "sanitize_query": ".query_guard",
}

install(sys.modules[__name__], _EXPORTS)
