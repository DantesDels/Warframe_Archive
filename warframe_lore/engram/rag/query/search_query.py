"""Preparation of the SEARCH query (alias-expanded, anaphora resolved).

Single responsibility: build the query that is actually embedded.  An anaphoric
question ("…cette histoire évoquée plus haut ?") is rewritten into a standalone
SEARCH query using the caller-owned context; the model only ever sees the user's
original wording.  Without a rewriter, the last established question is
concatenated (deterministic fallback) and the question is remembered.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..context import RAGContext
from .query_guard import _is_anaphoric

if TYPE_CHECKING:
    from .rewriter import QueryRewriter


async def search_query(question: str, context: RAGContext,
                       rewriter: QueryRewriter | None = None) -> str:
    """Standalone search query for ``question`` (already alias-expanded)."""
    if rewriter is not None:
        return await rewriter.rewrite(context, question, _is_anaphoric(question))
    if _is_anaphoric(question) and context.last_question:
        return f"{context.last_question} {question}"
    context.remember(question)
    return question


__all__ = ["search_query"]
