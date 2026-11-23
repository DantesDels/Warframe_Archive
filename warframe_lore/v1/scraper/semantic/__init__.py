"""Public API for Phase P3 semantic extraction and GraphRAG exports."""

from __future__ import annotations

from .aliases import resolve_aliases
from .export import KIND_TO_GRAPH, export_graphrag_bundle, semantic_to_graph_dict
from .llm_extract import enrich_chunk_with_llm
from .models import (
    ENTITY_TYPES,
    RELATION_TYPES,
    Entity,
    Mention,
    Relation,
    SemanticBundle,
    canonical_key,
    stable_id,
)
from .pipeline import extract_docs_semantics, extract_universe_semantics
from .rules import doc_taxonomy, extract_chunk_rules

__all__ = [
    "ENTITY_TYPES",
    "KIND_TO_GRAPH",
    "RELATION_TYPES",
    "Entity",
    "Mention",
    "Relation",
    "SemanticBundle",
    "canonical_key",
    "doc_taxonomy",
    "enrich_chunk_with_llm",
    "export_graphrag_bundle",
    "extract_chunk_rules",
    "extract_docs_semantics",
    "extract_universe_semantics",
    "resolve_aliases",
    "semantic_to_graph_dict",
    "stable_id",
]
