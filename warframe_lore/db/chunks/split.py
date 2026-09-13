"""``ChunkManager``: structural chunking (pass 1) + dialogue.

Pass 1 - structural (markdown-aware): delegated to
:mod:`warframe_lore.db.chunks.sections` (heading hierarchy captured as
metadata, recursive split with overlap on each block).

Pass 3 - semantic enrichment: when a ``page_title`` is given, each chunk
is prefixed with its context ``"Page: X | Section: Y - "`` so that the
vectorized text carries the page/section it comes from. The same format is
re-exported as structured sections (``sections_from_markdown``) consumed by
the ingestion pipeline (``ChunkManager.from_sections``).

Dialogue mode: delegated to :mod:`warframe_lore.db.chunks.dialogue`
(whole sessions, ``metadata["speakers"]``).
"""

from __future__ import annotations

from typing import Any

from .dialogue import _split_dialogue_lines
from .model import (
    DEFAULT_CHUNK_MAX_CHARACTERS,
    DEFAULT_CHUNK_OVERLAP_CHARACTERS,
    DEFAULT_DIALOGUE_CHUNK_MAX_CHARACTERS,
    DEFAULT_DIALOGUE_CHUNK_OVERLAP_CHARACTERS,
    RAGChunk,
)
from .patterns import strip_kim_chunk_meta
from .sections import (
    _context_prefix,
    _recursive_split,
    _section_chain,
    _split_on_heading_blocks,
    _strip_heading_lines,
)


class ChunkManager:
    """Splits cleaned Markdown into semantic chunks + metadata.

    Args:
        chunk_max_characters: target size of a chunk (pass 2).
        chunk_overlap_characters: overlap between consecutive chunks.
        dialogue_chunk_max_characters: target size in dialogue mode.
        dialogue_chunk_overlap_characters: overlap in dialogue mode.
    """

    def __init__(
        self,
        chunk_max_characters: int = DEFAULT_CHUNK_MAX_CHARACTERS,
        chunk_overlap_characters: int = DEFAULT_CHUNK_OVERLAP_CHARACTERS,
        dialogue_chunk_max_characters: int = (
            DEFAULT_DIALOGUE_CHUNK_MAX_CHARACTERS),
        dialogue_chunk_overlap_characters: int = (
            DEFAULT_DIALOGUE_CHUNK_OVERLAP_CHARACTERS),
    ) -> None:
        self.chunk_max_characters = chunk_max_characters
        self.chunk_overlap_characters = chunk_overlap_characters
        self.dialogue_chunk_max_characters = dialogue_chunk_max_characters
        self.dialogue_chunk_overlap_characters = (
            dialogue_chunk_overlap_characters)

    # ------------------------------------------------------------------ split
    def split(self, markdown_text: str, is_dialogue: bool = False,
              page_title: str = "") -> list[RAGChunk]:
        """Splits Markdown into ordered chunks (0-based chunk_index).

        Args:
            page_title: when given, each chunk is prefixed with its context
                (``"Page: X | Section: Y - "``) and the heading line itself
                is dropped from the body (deduplicated with the prefix).
                Without it, the legacy output (raw text, Heading metadata)
                is preserved unchanged.
        """
        if markdown_text:
            markdown_text = strip_kim_chunk_meta(markdown_text)
        if not markdown_text or not markdown_text.strip():
            return []

        if is_dialogue:
            return self._split_dialogue(markdown_text, page_title)

        # Pass 1 -- structural blocks with heading hierarchy.
        structural_blocks = _split_on_heading_blocks(markdown_text)

        chunks: list[RAGChunk] = []
        for block, headers in structural_blocks:
            if page_title:
                # The heading line becomes the "Section: Y" of the prefix:
                # it must not be duplicated in the vectorized body.
                block = _strip_heading_lines(block)
            block_sections = _recursive_split(
                block, self.chunk_max_characters,
                self.chunk_overlap_characters)
            for section_text in block_sections:
                if not section_text.strip():
                    continue
                if page_title:
                    section_name = _section_chain(headers)
                    content = _context_prefix(
                        page_title, section_name) + section_text.strip()
                    metadata = dict(headers)
                    metadata["page_title"] = page_title
                    if section_name:
                        metadata["section"] = section_name
                else:
                    content = section_text.strip()
                    metadata = dict(headers)
                chunks.append(RAGChunk(
                    chunk_index=len(chunks),
                    content_markdown=content,
                    metadata=metadata,
                ))
        return chunks

    # ----------------------------------------------------------- from sections
    def from_sections(self, sections: list[dict[str, Any]] | None
                      ) -> list[RAGChunk]:
        """Builds chunks directly from the parser's structured sections.

        Accepts the list of dictionaries emitted by the scraper/parser
        (and consumed by the ingestion pipeline):
        ``{"titre_page" | "page_title", "section", "contenu" | "content"}``.

        ``contenu`` must be the RAW section body: the context prefix is
        re-injected here so that the vectorized text format stays
        centralized (``Page: X | Section: Y - ...``).
        """
        chunks: list[RAGChunk] = []
        for section in sections or []:
            title = section.get("titre_page") or section.get("page_title") or ""
            section_name = (section.get("section") or "").strip()
            body = (section.get("contenu") or section.get("content") or "").strip()
            if not body:
                continue
            if title and not body.startswith("Page:"):
                content = _context_prefix(title, section_name) + body
            else:
                content = body
            metadata: dict[str, Any] = {}
            if title:
                metadata["page_title"] = title
            if section_name:
                metadata["section"] = section_name
            chunks.append(RAGChunk(
                chunk_index=len(chunks),
                content_markdown=content,
                metadata=metadata,
            ))
        return chunks

    # ----------------------------------------------------------- dialogue
    def _split_dialogue(self, markdown_text: str, page_title: str = ""
                        ) -> list[RAGChunk]:
        return _split_dialogue_lines(
            markdown_text, page_title,
            self.dialogue_chunk_max_characters,
            self.dialogue_chunk_overlap_characters)


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

    ``contenu`` is the RAW section body -- WITHOUT the context prefix
    (it is re-injected by ``from_sections`` so the vectorized format stays
    centralized).  A long section may yield several entries (the recursive
    pass applies), each one carrying its own section label.
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
