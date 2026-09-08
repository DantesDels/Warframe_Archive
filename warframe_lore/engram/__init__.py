"""ENGRAM — infrastructure RAG & API du lore Warframe.

Sous-paquet du projet : fournit un backend de recherche documentaire
(similarité cosinus pgvector sur ``lore_chunks``) et un terminal Roleplay
KIM temps réel (WebSocket, streaming token, sliding window).

Organisation :
    * ``config``  -> :class:`EngramConfig` (connexions, modèles, fenêtres) ;
    * ``llm``     -> fournisseurs LLM/embedding locaux (LM Studio) ;
    * ``rag``     -> recherche vectorielle + construction de prompt ;
    * ``roleplay``-> sessions KIM + streaming (sliding window) ;
    * ``api``     -> application FastAPI (routes RAG + Roleplay WS) ;
    * ``scripts`` -> ETL d'ingestion (``ingest.py``) ;
    * ``models``  -> dataclasses de transport (un fichier par classe).
"""

from __future__ import annotations

from .config import EngramConfig
from .persona import Persona

__all__ = ["EngramConfig", "Persona"]
