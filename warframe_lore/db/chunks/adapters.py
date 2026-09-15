"""Convenience adapters over :class:`ChunkManager`.

Single responsibility: the two call shapes used outside the chunking package —
the legacy ``chunk_markdown`` API (plain text blocks, no metadata) and
``sections_from_markdown``, the structured parser output consumed by the
ingestion pipeline (``ChunkManager.from_sections``).  No chunking rule lives
here: both delegate to the manager so the vectorized format stays centralized.
"""

from __future__ import annotations

from .model import DEFAULT_CHUNK_MAX_CHARACTERS, DEFAULT_CHUNK_OVERLAP_CHARACTERS
from .sections import _context_prefix
from .split import ChunkManager


def chunk_markdown(
    markdown_text: str,
    chunk_max_characters: int = DEFAULT_CHUNK_MAX_CHARACTERS,
    chunk_overlap_characters: int = DEFAULT_CHUNK_OVERLAP_CHARACTERS,
) -> list[str]:
    """Splits Markdown into blocks (legacy API, no metadata)."""
    manager = ChunkManager(
        chunk_max_characters=chunk_max_characters,
        chunk_overlap_characters=chunk_overlap_characters,
    )
    return [chunk.content_markdown
            for chunk in manager.split(markdown_text, is_dialogue=False)]


def sections_from_markdown(
    markdown_text: str,
    page_title: str = "",
    chunk_max_characters: int = DEFAULT_CHUNK_MAX_CHARACTERS,
    chunk_overlap_characters: int = DEFAULT_CHUNK_OVERLAP_CHARACTERS,
) -> list[dict[str, str]]:
    """Decomposes a cleaned page into iterative semantic sections.

    This is the structured output of the parsing phase, consumed by the
    ingestion pipeline (``ChunkManager.from_sections``): each returned dict
    follows ``{"titre_page": ..., "section": ..., "contenu": ...}``.

    ``contenu`` is the RAW section body — WITHOUT the context prefix (it is
    re-injected by ``from_sections`` so the vectorized format stays
    centralized).  A long section may yield several entries (the recursive pass
    applies), each one carrying its own section label.
    """
    manager = ChunkManager(
        chunk_max_characters=chunk_max_characters,
        chunk_overlap_characters=chunk_overlap_characters,
    )
    sections: list[dict[str, str]] = []
    for chunk in manager.split(markdown_text, is_dialogue=False,
                               page_title=page_title):
        title = chunk.metadata.get("page_title", "")
        section_name = chunk.metadata.get("section", "")
        prefix = _context_prefix(title, section_name) if title else ""
        body = chunk.content_markdown
        if prefix and body.startswith(prefix):
            body = body[len(prefix):]
        sections.append({
            "titre_page": title,
            "section": section_name,
            "contenu": body.strip(),
        })
    return sections


__all__ = ["chunk_markdown", "sections_from_markdown"]
