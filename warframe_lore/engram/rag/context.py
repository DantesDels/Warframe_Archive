"""Ephemeral RAG conversational memory (per request / per connection).

Isolation contract: a :class:`RAGService` holds NO conversational state.
The only memory — anaphora search enrichment ("that story mentioned
earlier?") — lives in a :class:`RAGContext` created by the CALLER:

  * HTTP document route: fresh context per request via ``Depends``
    (``api/deps.py``), nothing survives the request;
  * Roleplay WebSocket: one context per connection (per user), created at
    session start and garbage-collected at connection close;
  * unit tests: the caller passes a context explicitly when several turns
    must share memory.

No global dict, no singleton cache, no ``_last_query`` on the shared
service: cross-request / cross-user context bleeding becomes structurally
impossible.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

# Per-user context window (most recent questions) feeding the search rewrite.
WINDOW_SIZE = 3


@dataclass
class RAGContext:
    """Request/session-scoped memory for anaphora search enrichment."""

    user_key: str | None = None
    # Recent questions (sliding window), fed to the micro-rewrite call.
    recent: deque[str] = field(
        default_factory=lambda: deque(maxlen=WINDOW_SIZE))
    # Last established question: lexical enrichment for the legacy
    # concatenation fallback (no QueryRewriter).
    last_question: str | None = None

    def remember(self, question: str) -> None:
        """Records a question in the window and as the last established one."""
        if self.recent and self.recent[-1] == question:
            return
        self.recent.append(question)
        self.last_question = question

    def history(self) -> list[str]:
        """Previous questions (before the current one), oldest first."""
        return list(self.recent)

    def clear(self) -> None:
        """Forgets the window (new discussion / user switch)."""
        self.recent.clear()
        self.last_question = None


class RAGContextFactory:
    """Creates fresh, isolated contexts (FastAPI ``Depends`` provider)."""

    @staticmethod
    def create(user_key: str | None = None) -> RAGContext:
        return RAGContext(user_key=user_key)


__all__ = ["RAGContext", "RAGContextFactory", "WINDOW_SIZE"]