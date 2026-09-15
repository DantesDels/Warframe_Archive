"""Lore-question detection: is a RAG retrieval worth it?

Decides whether a message looks like a document-based question about the
Warframe universe.  Bilingual FR/EN — the Oracle answers English input too.
Introspection (the Oracle itself, its creator) is excluded on purpose: the
no-passage short-circuit would answer "[Archives] Données insuffisantes…"
instead of letting the persona use its consciousness exception.

Pure module: no discord.py dependency, no I/O.
"""

from __future__ import annotations

from warframe_lore.engram.rag import is_self_reflection

# Trigger words of a document-based question (a retrieval is worth it).
LORE_TRIGGERS = (
    "qui ", "qu'est", "quel", "quelle", "quand", "où ", "comment",
    "pourquoi", "combien", "histoir", "lore", "orokin", "tenno",
    "warframe", "primordial", "hex", "void", "kuva", "infest",
    "fragments", "chimer", "trésors", "règne",
    # English equivalents
    "who ", "what ", "when ", "where ", "why ", "which ", "whose ",
    "how ", "how many", "how much", "tell me about", "history",
    "who 's", "what 's", "when 's", "where 's",
)


def wants_lore(text: str) -> bool:
    """True when the input looks like a lore question (useful RAG)."""
    if is_self_reflection(text):
        return False
    low = (text or "").lower()
    return any(trigger in low for trigger in LORE_TRIGGERS)


__all__ = ["LORE_TRIGGERS", "wants_lore"]
