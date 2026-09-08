"""Schémas HTTP de l'API ENGRAM (couche transport uniquement)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RAGRequest:
    """Corps de la route documentaire."""

    question: str
    stream: bool = False


@dataclass
class SourceDocument:
    """Passage pertinent, exposé comme source au client."""

    page_title: str
    content: str
    score: float


@dataclass
class RAGResponse:
    """Réponse documentaire : réponse du modèle + sources."""

    answer: str
    sources: list[SourceDocument] = field(default_factory=list)