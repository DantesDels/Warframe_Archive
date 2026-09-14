"""Prompt RAG et chaînes de garde partagées avec le Roleplay.

Façade PARESSEUSE du sous-paquet (voir :mod:`warframe_lore.lazy_facade`) :
:mod:`builder` (template système strict en 3 blocs, assemblage du contexte
``<archives>``) et :mod:`guards` (textes de sécurité, sans aucune dépendance —
le bot Discord et le Roleplay les importent directement).
"""

from __future__ import annotations

import sys

from warframe_lore.lazy_facade import install

_EXPORTS = {
    "ARCHIVES_REPLY": ".guards",
    "HALLUCINATION_GUARD": ".guards",
    "HIERARCHY_BLOCK": ".guards",
    "JAILBREAK_BLOCK": ".guards",
    "JAILBREAK_REJECT": ".guards",
    "LOGICAL_INFERENCE_BLOCK": ".guards",
    "NO_DATA_MARKER": ".builder",
    "OFF_TOPIC_ERROR": ".guards",
    "OFF_TOPIC_REPLY": ".guards",
    "PromptBuilder": ".builder",
    "RAGPrompt": ".builder",
    "RAG_ERROR": ".guards",
    "RAG_SYSTEM_TEMPLATE": ".builder",
    "RELATIONSHIP_ISOLATION_BLOCK": ".guards",
    "SUGGESTION_DIRECTIVE": ".builder",
    "SUGGESTION_MARKER": ".builder",
}

install(sys.modules[__name__], _EXPORTS)
