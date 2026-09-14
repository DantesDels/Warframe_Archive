"""Document RAG: analyse de requête, retrieval, prompt, orchestration.

Façade STABLE du paquet : les chemins internes peuvent bouger, les noms publics
restent importables d'ici.  Organisation par domaine —

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

from .context import RAGContext, RAGContextFactory
from .prompt import (
    ARCHIVES_REPLY,
    HALLUCINATION_GUARD,
    HIERARCHY_BLOCK,
    JAILBREAK_BLOCK,
    JAILBREAK_REJECT,
    LOGICAL_INFERENCE_BLOCK,
    NO_DATA_MARKER,
    OFF_TOPIC_ERROR,
    OFF_TOPIC_REPLY,
    RAG_ERROR,
    RAG_SYSTEM_TEMPLATE,
    RELATIONSHIP_ISOLATION_BLOCK,
    SUGGESTION_DIRECTIVE,
    SUGGESTION_MARKER,
    PromptBuilder,
    RAGPrompt,
)
from .query import (
    ALIASES,
    AliasResolver,
    QueryRewriter,
    detect_probe,
    is_identity_question,
    is_self_reflection,
    resolve_alias,
    sanitize_query,
)
from .retrieval import (
    CosinusSearch,
    HybridHit,
    HybridQuery,
    HybridSearch,
    RAGHit,
    Retriever,
    query_terms,
    set_hnsw_ef_search,
    strip_context_prefix,
    ts_rank_normalized,
)
from .sanitize import strip_trailing_padding
from .service import RAGService

__all__ = [
    "ALIASES", "ARCHIVES_REPLY", "AliasResolver", "CosinusSearch",
    "HALLUCINATION_GUARD", "HIERARCHY_BLOCK", "HybridHit", "HybridQuery",
    "HybridSearch", "JAILBREAK_BLOCK", "JAILBREAK_REJECT",
    "LOGICAL_INFERENCE_BLOCK", "NO_DATA_MARKER", "OFF_TOPIC_ERROR",
    "OFF_TOPIC_REPLY", "PromptBuilder", "QueryRewriter", "RAGContext",
    "RAGContextFactory", "RAGHit", "RAGPrompt", "RAGService", "RAG_ERROR",
    "RAG_SYSTEM_TEMPLATE", "RELATIONSHIP_ISOLATION_BLOCK", "Retriever",
    "SUGGESTION_DIRECTIVE", "SUGGESTION_MARKER", "detect_probe",
    "is_identity_question", "is_self_reflection", "query_terms", "resolve_alias",
    "sanitize_query", "set_hnsw_ef_search", "strip_context_prefix",
    "strip_trailing_padding", "ts_rank_normalized",
]
