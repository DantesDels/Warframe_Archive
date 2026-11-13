"""Retrieval strategies by intent: Codex (hybrid + rerank) vs Story (chrono).

Façade PARESSEUSE du sous-paquet (voir :mod:`warframe_lore.lazy_facade`) :
les modules SQLAlchemy ne sont chargés qu'au premier accès.
"""

from __future__ import annotations

import sys

from warframe_lore.lazy_facade import install

_EXPORTS = {
    "CODEX_LEXICAL_CANDIDATES": ".codex",
    "CODEX_TOP_N": ".codex",
    "CodexRoute": ".codex",
    "LexicalChannel": ".codex",
    "Reranker": ".rerank",
    "RetrievalIntent": ".intent",
    "RetrievalRouter": ".router",
    "STORY_ORDERED_LIMIT": ".story",
    "STORY_VECTOR_CANDIDATES": ".story",
    "SimulatedCrossEncoderReranker": ".rerank",
    "StoryRoute": ".story",
    "classify_intent": ".intent",
    "story_statement": ".story",
}

install(sys.modules[__name__], _EXPORTS)
