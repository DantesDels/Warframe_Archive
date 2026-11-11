"""Central abstract protocols and contracts for Cephalon Archive.

Following the Dependency Inversion Principle (SOLID / D), high-level services
depend strictly on these abstract interfaces rather than concrete databases
or network clients.
"""

from __future__ import annotations

from .llm import EmbeddingProvider, LLMProvider
from .retriever import DossierPage, RAGHit, Retriever
from .roleplay import (
    FRAME_COMMENT,
    FRAME_END,
    FRAME_ERROR,
    FRAME_MESSAGE,
    FRAME_OPEN,
    FRAME_PERSONA,
    FRAME_RESET,
    FRAME_TOKEN,
    STORY_DOSSIER_PAGE,
    CommentFrame,
    CommentRequestFrame,
    EndFrame,
    ErrorFrame,
    MessageFrame,
    OpenFrame,
    PersonaFrame,
    ResetFrame,
    TokenFrame,
    TurnOutcome,
)

__all__ = [
    "CommentFrame",
    "CommentRequestFrame",
    "DossierPage",
    "EmbeddingProvider",
    "EndFrame",
    "ErrorFrame",
    "FRAME_COMMENT",
    "FRAME_END",
    "FRAME_ERROR",
    "FRAME_MESSAGE",
    "FRAME_OPEN",
    "FRAME_PERSONA",
    "FRAME_RESET",
    "FRAME_TOKEN",
    "LLMProvider",
    "MessageFrame",
    "OpenFrame",
    "PersonaFrame",
    "RAGHit",
    "ResetFrame",
    "Retriever",
    "STORY_DOSSIER_PAGE",
    "TokenFrame",
    "TurnOutcome",
]
