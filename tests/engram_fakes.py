"""Conteneur ENGRAM factice : piloter ``plan_turn`` sans WebSocket ni LLM.

Partagé par les tests de la décision de tour (``test_roleplay_turn`` et
``test_roleplay_turn_member``) : un RAG scripté qui rend un contexte fixé et
journalise les appels, ce qui permet d'assertionner autant la réponse que
l'ABSENCE de récupération documentaire.
"""

from __future__ import annotations

import asyncio

from warframe_lore.engram.rag import RAGContext
from warframe_lore.engram.roleplay.turn import TurnPlan, plan_turn
from warframe_lore.protocols.roleplay import PERSONA_ORACLE


class FakeRAG:
    """RAG factice : rend un contexte fixé et journalise les questions."""

    def __init__(self, context=None, suggestion=None, more=False,
                 consumed=()) -> None:
        self.context = context
        self.suggestion = suggestion
        self.more = more
        self.consumed = list(consumed)
        self.calls: list[str] = []
        self.offsets: list[int] = []
        self.exclusions: list[list[int]] = []

    async def resolve(self, question: str, context=None, subject=None,
                      offset=0, exclude_ids=None):
        self.calls.append(question)
        self.offsets.append(offset)
        self.exclusions.append(list(exclude_ids or ()))
        return self.context, self.suggestion, self.more, self.consumed


class FakeContainer:
    """Conteneur minimal : seul le RAG est exercé par ``plan_turn``."""

    def __init__(self, rag=None) -> None:
        self.rag = rag if rag is not None else FakeRAG()


def decide(payload=None, text="bonjour", persona=PERSONA_ORACLE, rag=None,
           consumed=None) -> TurnPlan:
    """Un ``plan_turn`` exécuté sur conteneur factice (aucun réseau)."""
    container = FakeContainer(rag)
    return asyncio.new_event_loop().run_until_complete(
        plan_turn(container, payload or {}, text, persona, RAGContext(),
                  consumed_chunk_ids=consumed))


__all__ = ["FakeContainer", "FakeRAG", "decide"]
