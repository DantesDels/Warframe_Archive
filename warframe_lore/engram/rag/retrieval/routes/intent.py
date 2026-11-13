"""Intent classification for the two RAG routes.

Route A (CODEX) answers factual lookups ("Qui est Zikhaio Nuri ?").
Route B (STORY) answers narration requests ("Raconte-moi...", "Continue").
The explicit ``story`` flag sent by the bot always wins; otherwise a small,
deterministic marker list routes the wording — no LLM call is spent on it.
"""

from __future__ import annotations

from enum import StrEnum


class RetrievalIntent(StrEnum):
    """User intention that selects a retrieval strategy."""

    CODEX = "codex"
    STORY = "story"


_STORY_MARKERS = (
    "raconte",
    "histoire",
    "récit",
    "recit",
    "narre",
    "continue",
    "la suite",
    "poursuis",
    "go on",
    "keep going",
)


def classify_intent(question: str, story: bool = False) -> RetrievalIntent:
    """Route a question to the Codex or Story strategy.

    ``story=True`` (explicit bot flag) takes precedence; otherwise the
    wording is matched against narration markers.  Everything else is a
    factual Codex lookup.
    """
    if story:
        return RetrievalIntent.STORY
    wording = question.casefold()
    if any(marker in wording for marker in _STORY_MARKERS):
        return RetrievalIntent.STORY
    return RetrievalIntent.CODEX


__all__ = ["RetrievalIntent", "classify_intent"]
