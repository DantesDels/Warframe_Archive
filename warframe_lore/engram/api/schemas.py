"""ENGRAM API HTTP schemas (transport layer only)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RAGRequest:
    """Document route request body."""

    question: str
    stream: bool = False


@dataclass
class SourceDocument:
    """Relevant passage, exposed as a source to the client."""

    page_title: str
    content: str
    score: float


@dataclass
class RAGResponse:
    """Document response: model answer + sources."""

    answer: str
    sources: list[SourceDocument] = field(default_factory=list)