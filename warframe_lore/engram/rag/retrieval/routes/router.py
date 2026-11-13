"""Dispatch a retrieval to the Codex or Story strategy.

Single responsibility: pick the route from the classified intent and call it.
Both routes expose the same ``retrieve(question, query_vector)`` contract, so
the pipeline never knows which strategy ran (Open/Closed: a third route only
requires a new branch here).
"""

from __future__ import annotations

from warframe_lore.engram.rag.retrieval.retriever import RAGHit
from warframe_lore.engram.rag.retrieval.routes.codex import CodexRoute
from warframe_lore.engram.rag.retrieval.routes.intent import (
    RetrievalIntent,
    classify_intent,
)
from warframe_lore.engram.rag.retrieval.routes.story import StoryRoute


class RetrievalRouter:
    """Routes one retrieval to the strategy matching the user intent."""

    def __init__(self, codex: CodexRoute, story: StoryRoute) -> None:
        self.codex = codex
        self.story = story

    async def retrieve(self, question: str, query_vector: list[float], *,
                       story: bool = False) -> list[RAGHit]:
        """Retrieve with the route selected by ``classify_intent``."""
        intent = classify_intent(question, story)
        route = self.story if intent is RetrievalIntent.STORY else self.codex
        return await route.retrieve(question, query_vector)


__all__ = ["RetrievalRouter"]
