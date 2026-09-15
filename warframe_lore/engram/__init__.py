"""ENGRAM — Warframe lore RAG & API infrastructure.

Project sub-package: provides a document search backend (cosine similarity
via pgvector on ``lore_chunks``) and a real-time KIM Roleplay terminal
(WebSocket, token streaming, sliding window).

Organization:
    * ``config``   -> :class:`EngramConfig` (connections, models, windows);
    * ``llm``      -> local LLM/embedding providers (LM Studio);
    * ``rag``      -> vector search + prompt construction;
    * ``roleplay`` -> KIM sessions + streaming (sliding window);
    * ``api``      -> FastAPI application (RAG routes + Roleplay WS);
    * ``scripts``  -> ingestion ETL (``ingest.py``);
    * ``models``   -> transport dataclasses (one file per class).
"""

from __future__ import annotations

from .config import EngramConfig
from .persona import Persona

__all__ = ["EngramConfig", "Persona"]
