"""Prompt RAG et chaînes de garde partagées avec le Roleplay.

Façade du sous-paquet : :mod:`builder` (template système strict en 3 blocs,
assemblage du contexte ``<archives>``) et :mod:`guards` (textes de sécurité —
rejet anti-jailbreak, garde d'hallucination, immunité hiérarchique).  Les noms
publics restent importables depuis ``warframe_lore.engram.rag``.
"""

from __future__ import annotations

from .builder import (
    NO_DATA_MARKER,
    RAG_SYSTEM_TEMPLATE,
    SUGGESTION_DIRECTIVE,
    SUGGESTION_MARKER,
    PromptBuilder,
    RAGPrompt,
)
from .guards import (
    ARCHIVES_REPLY,
    HALLUCINATION_GUARD,
    HIERARCHY_BLOCK,
    JAILBREAK_BLOCK,
    JAILBREAK_REJECT,
    LOGICAL_INFERENCE_BLOCK,
    OFF_TOPIC_ERROR,
    OFF_TOPIC_REPLY,
    RAG_ERROR,
    RELATIONSHIP_ISOLATION_BLOCK,
)

__all__ = [
    "ARCHIVES_REPLY", "HALLUCINATION_GUARD", "HIERARCHY_BLOCK",
    "JAILBREAK_BLOCK", "JAILBREAK_REJECT", "LOGICAL_INFERENCE_BLOCK",
    "NO_DATA_MARKER", "OFF_TOPIC_ERROR", "OFF_TOPIC_REPLY", "RAG_ERROR",
    "RAG_SYSTEM_TEMPLATE", "RELATIONSHIP_ISOLATION_BLOCK", "SUGGESTION_DIRECTIVE",
    "SUGGESTION_MARKER", "PromptBuilder", "RAGPrompt",
]
