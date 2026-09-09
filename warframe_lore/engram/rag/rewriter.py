"""Per-user search query rewriting (anaphora resolution).

Long-distance references ("...this PS5 story mentioned earlier?") retrieve
poorly in vector space because they name no entity.  Instead of the single
global ``last_query`` concatenation, this module keeps a per-user window of
recent questions and — only when the input is anaphoric — asks a *micro* LLM
call to produce a standalone search query.

Guarantees:
  * the rewritten text is used for the EMBEDDING / pgvector search ONLY;
    the model never sees it (the prompt keeps the user's exact wording);
  * the call happens only for anaphoric inputs (cheap, bounded): plain
    questions are stored and relayed unchanged, with zero model cost;
  * on any LLM failure the concatenation fallback (last query + current
    question) is used, mirroring the historical behaviour.
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import AsyncIterator

from ..llm import LLMProvider
from ..models import ChatMessage

log = logging.getLogger("warframe_lore.engram.rag.rewriter")

# Per-user context window (most recent questions) feeding the rewrite.
WINDOW_SIZE = 3
# The micro call is bounded: a short standalone query is enough.
REWRITE_MAX_TOKENS = 96
REWRITE_TEMPERATURE = 0.0

_SYSTEM = (
    "Tu es un réécrisseur de recherche. Reformule la dernière question "
    "de l'utilisateur en une requête de recherche autonome et autonome, en "
    "résolvant toutes les références (pronoms, 'cette histoire', 'ce sujet', "
    "etc.) grâce aux échanges précédents. Réponds UNIQUEMENT avec la requête "
    "réécrite, sans guillemets, sans explication, sans préfixe."
)


class QueryRewriter:
    """Per-user recent-question window with LLM-assisted rewrite."""

    def __init__(self, llm: LLMProvider | None = None,
                 window_size: int = WINDOW_SIZE) -> None:
        self.llm = llm
        self.window_size = window_size
        self._recent: dict[str, deque[str]] = {}

    def remember(self, user_key: str, question: str) -> None:
        """Stores a plain question in the user's window (no model call)."""
        window = self._recent.setdefault(user_key, deque(maxlen=self.window_size))
        if window and window[-1] == question:
            return
        window.append(question)

    def history(self, user_key: str) -> list[str]:
        return list(self._recent.get(user_key, ()))

    def clear(self, user_key: str) -> None:
        """Forgets the user's recent questions (new discussion)."""
        self._recent.pop(user_key, None)

    async def rewrite(self, user_key: str, question: str,
                      is_anaphoric: bool) -> str:
        """Returns the SEARCH query: rewritten (anaphoric) or verbatim.

        ``is_anaphoric`` is decided by the caller (``service._is_anaphoric``)
        so that this module stays heuristic-free.  When no rewrite is needed,
        the question is relayed verbatim and memorised for later.
        """
        if not is_anaphoric:
            self.remember(user_key, question)
            return question
        history = self.history(user_key)
        self.remember(user_key, question)
        if not history:
            # Anaphora with no previous turn in this window: nothing to
            # resolve — the verbatim question is the best search query.
            return question
        rewritten = await self._call_llm(history, question)
        if rewritten:
            return rewritten
        # Fallback: concatenation (resolves the reference lexically).
        return f"{history[-1]} {question}"

    async def _call_llm(self, history: list[str], question: str) -> str | None:
        """Micro LLM call producing a standalone search query (or None)."""
        if self.llm is None:
            return None
        previous = "\n".join(f"- {q}" for q in history)
        user = (
            f"Échanges précédents:\n{previous}\n"
            f"\nDernière question: {question}\n\nRequête de recherche:")
        messages = [ChatMessage("system", _SYSTEM),
                    ChatMessage("user", user)]
        tokens: list[str] = []
        try:
            async for token in self._stream(messages):
                tokens.append(token)
        except Exception as exc:  # noqa: BLE001 (LLM down -> fallback)
            log.warning("Query rewrite failed (%s) — concatenation fallback",
                        exc)
            return None
        rewritten = " ".join(tokens).strip()
        return rewritten if rewritten else None

    async def _stream(self, messages: list[ChatMessage]
                      ) -> AsyncIterator[str]:
        """Streams the rewrite through the injected LLM provider."""
        async for token in self.llm.chat_stream(
                messages, temperature=REWRITE_TEMPERATURE):
            yield token


__all__ = ["QueryRewriter"]