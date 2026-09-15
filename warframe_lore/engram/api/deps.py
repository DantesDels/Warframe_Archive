"""Request-scoped dependencies (FastAPI DI).

Every HTTP request receives a FRESH ephemeral :class:`RAGContext` via
``Depends``: the shared :class:`RAGService` is stateless, so no
conversational memory survives the end of an async request (context
bleeding elimination). The Roleplay WebSocket cannot use ``Depends`` (one
connection == one long-lived async request): its router builds ONE context
per connection instead (see ``routers/roleplay.py``).
"""

from __future__ import annotations

from ..rag import RAGContext, RAGContextFactory


def get_rag_context() -> RAGContext:
    """Fresh, request-scoped RAG memory (no identity on the HTTP route).

    A new object per call: nothing is shared between two requests, even on
    the same service instance.
    """
    return RAGContextFactory.create(user_key=None)


__all__ = ["get_rag_context"]
