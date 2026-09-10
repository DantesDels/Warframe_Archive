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


@dataclass
class SearchHit:
    """One chunk surfaced by the hybrid search (RAG Inspector)."""

    chunk_id: int
    page_title: str
    section: str
    content: str
    metadata: dict
    cosine_score: float | None
    ts_score: float | None
    score: float
    headline: str


@dataclass
class SearchDebug:
    """Exact LLM payload as assembled today (context-bleed audit)."""

    system: str
    context: str
    user_question: str
    messages: list[dict]


@dataclass
class SearchResponse:
    """Hybrid search response: alias context + chunk hits (+ optional debug)."""

    query: str
    search_question: str
    alias_note: str
    alias_active: bool
    canonical: str
    highlight_terms: list[str]
    hits: list[SearchHit] = field(default_factory=list)
    debug: SearchDebug | None = None