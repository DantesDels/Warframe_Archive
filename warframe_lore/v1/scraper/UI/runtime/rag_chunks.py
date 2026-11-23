"""Section-aware chunk generation for LLM/RAG export writers."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ...use_cases.pipeline.chunking import chunk_text as _chunk


def iter_doc_chunks(doc: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """Yield (text, section_title) pairs, preferring structured sections."""
    sections = doc.get("sections")
    if isinstance(sections, list) and sections:
        for section in sections:
            if not isinstance(section, dict):
                continue
            title = str(section.get("section") or "")
            content = str(section.get("contenu") or "").strip()
            for chunk in _chunk(content):
                if chunk.strip():
                    yield chunk, title
        return
    fallback = str(doc.get("content_markdown") or doc.get("content") or "")
    for chunk in _chunk(fallback):
        yield chunk, ""
