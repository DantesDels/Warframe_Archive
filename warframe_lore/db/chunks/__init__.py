"""Découpage RAG : interface publique du sous-paquet ``chunks``.

Ré-exporte le ``ChunkManager``, les constantes de taille, le type ``RAGChunk``
et l'ancienne API ``chunk_markdown``.

Implémentation répartie entre :
    * ``split``      — ``ChunkManager`` (structurel + dialogue) ;
    * ``splitters``  — splitters récursifs + chevauchement + locuteurs ;
    * ``patterns``   — purge des pointeurs de navigation KIM.
"""

from __future__ import annotations

from .split import (
    DEFAULT_CHUNK_MAX_CHARACTERS,
    DEFAULT_CHUNK_OVERLAP_CHARACTERS,
    DEFAULT_DIALOGUE_CHUNK_MAX_CHARACTERS,
    DEFAULT_DIALOGUE_CHUNK_OVERLAP_CHARACTERS,
    ChunkManager,
    RAGChunk,
    chunk_markdown,
)

__all__ = [
    "DEFAULT_CHUNK_MAX_CHARACTERS",
    "DEFAULT_CHUNK_OVERLAP_CHARACTERS",
    "DEFAULT_DIALOGUE_CHUNK_MAX_CHARACTERS",
    "DEFAULT_DIALOGUE_CHUNK_OVERLAP_CHARACTERS",
    "ChunkManager",
    "RAGChunk",
    "chunk_markdown",
]