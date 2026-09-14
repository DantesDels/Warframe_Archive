"""Document RAG: analyse de requête, retrieval, prompt, orchestration.

Façade STABLE et PARESSEUSE : les noms publics sont résolus au premier accès
(PEP 562, voir :mod:`warframe_lore.lazy_facade`), donc importer le paquet
n'entraîne ni SQLAlchemy, ni les providers LLM.  Un consommateur léger (le bot
Discord n'utilise que les chaînes de garde et les sondes de requête) ne charge
que ce dont il a besoin, et les chemins internes restent libres d'évoluer.

Organisation par domaine —

    * ``query/``     -> sonde hostile et questions (``probes``), sanitisation et
                        garde d'entité (``query_guard``), aliases (``aliases``),
                        réécriture de requête (``rewriter``) ;
    * ``retrieval/`` -> contrat ``Retriever``/``RAGHit``, cosinus pgvector
                        (``search``), hybride vectoriel + plein texte (``hybrid``) ;
    * ``prompt/``    -> template système et assemblage (``builder``), chaînes de
                        garde partagées avec le Roleplay (``guards``) ;
    * ``context.py`` -> mémoire conversationnelle éphémère par requête ;
    * ``sanitize.py``-> purge des artefacts de formatage en sortie ;
    * ``service.py`` -> :class:`RAGService` (orchestration sur abstractions).
"""

from __future__ import annotations

import sys

from warframe_lore.lazy_facade import install

# Nom public -> module relatif qui le définit (table de données, §3.1).
_EXPORTS = {
    "ALIASES": ".query.aliases",
    "ARCHIVES_REPLY": ".prompt.guards",
    "AliasResolver": ".query.aliases",
    "CosinusSearch": ".retrieval.search",
    "HALLUCINATION_GUARD": ".prompt.guards",
    "HIERARCHY_BLOCK": ".prompt.guards",
    "HybridHit": ".retrieval.hybrid",
    "HybridQuery": ".retrieval.hybrid",
    "HybridSearch": ".retrieval.hybrid",
    "JAILBREAK_BLOCK": ".prompt.guards",
    "JAILBREAK_REJECT": ".prompt.guards",
    "LOGICAL_INFERENCE_BLOCK": ".prompt.guards",
    "NO_DATA_MARKER": ".prompt.builder",
    "OFF_TOPIC_ERROR": ".prompt.guards",
    "OFF_TOPIC_REPLY": ".prompt.guards",
    "PromptBuilder": ".prompt.builder",
    "QueryRewriter": ".query.rewriter",
    "RAGContext": ".context",
    "RAGContextFactory": ".context",
    "RAGHit": ".retrieval.retriever",
    "RAGPrompt": ".prompt.builder",
    "RAGService": ".service",
    "RAG_ERROR": ".prompt.guards",
    "RAG_SYSTEM_TEMPLATE": ".prompt.builder",
    "RELATIONSHIP_ISOLATION_BLOCK": ".prompt.guards",
    "Retriever": ".retrieval.retriever",
    "SUGGESTION_DIRECTIVE": ".prompt.builder",
    "SUGGESTION_MARKER": ".prompt.builder",
    "detect_probe": ".query.probes",
    "is_identity_question": ".query.probes",
    "is_self_reflection": ".query.probes",
    "query_terms": ".retrieval.hybrid",
    "resolve_alias": ".query.aliases",
    "sanitize_query": ".query.query_guard",
    "set_hnsw_ef_search": ".retrieval.search",
    "strip_context_prefix": ".retrieval.hybrid",
    "strip_trailing_padding": ".sanitize",
    "ts_rank_normalized": ".retrieval.hybrid",
}

install(sys.modules[__name__], _EXPORTS)
