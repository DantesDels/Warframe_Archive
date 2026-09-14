"""Analyse de la requête entrante.

Façade du sous-paquet : sonde hostile et détecteurs de questions
(:mod:`probes`), garde d'entité et sanitisation (:mod:`query_guard`), aliases
mnémoniques (:mod:`aliases`), réécriture de requête (:mod:`rewriter`).  Les noms
publics restent importables depuis ``warframe_lore.engram.rag``.
"""

from __future__ import annotations

from .aliases import ALIASES, AliasResolver, resolve_alias
from .probes import detect_probe, is_identity_question, is_self_reflection
from .query_guard import sanitize_query
from .rewriter import QueryRewriter

__all__ = ["ALIASES", "AliasResolver", "QueryRewriter", "detect_probe",
           "is_identity_question", "is_self_reflection", "resolve_alias",
           "sanitize_query"]
