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
    FRAME_PING,
    FRAME_PONG,
    FRAME_RETRY,
    FRAME_TOKEN,
    KNOWN_FRAMES,
    ROLEPLAY_WS_PATH,
    ROLES,
    SYSTEM_ROLES,
    USER_ROLES,
    RoleplayFrame,
    RoleplayGatewayProtocol,
    RoleplaySessionProtocol,
)

__all__ = [
    "DossierPage",
    "EmbeddingProvider",
    "FRAME_COMMENT",
    "FRAME_END",
    "FRAME_ERROR",
    "FRAME_MESSAGE",
    "FRAME_OPEN",
    "FRAME_PERSONA",
    "FRAME_PING",
    "FRAME_PONG",
    "FRAME_RETRY",
    "FRAME_TOKEN",
    "KNOWN_FRAMES",
    "LLMProvider",
    "RAGHit",
    "ROLES",
    "ROLEPLAY_WS_PATH",
    "Retriever",
    "RoleplayFrame",
    "RoleplayGatewayProtocol",
    "RoleplaySessionProtocol",
    "SYSTEM_ROLES",
    "USER_ROLES",
]
