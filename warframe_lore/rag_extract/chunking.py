"""Semantic chunking: split cleaned page text into validated ``LoreChunk``.

The input is the sectioned Markdown produced by the extractors: each
``## Section`` / ``### Sub-section`` heading starts a logical block. The
lead (text before the first heading) becomes an "Introduction" section.
Undersized blocks are merged into the previous chunk so that every emitted
``LoreChunk`` satisfies ``content.min_length``.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .models import MIN_CONTENT_LENGTH, LoreChunk

logger = logging.getLogger(__name__)

HEADING_RE = re.compile(r"^(#{2,3})\s+(.+?)\s*$")
INTRODUCTION_TITLE = "Introduction"

__all__ = ["chunk_into_lorechunks", "INTRODUCTION_TITLE"]


def chunk_into_lorechunks(
    text: str,
    source_url: str,
    page_title: str,
    metadata: dict[str, Any] | None = None,
    min_length: int = MIN_CONTENT_LENGTH,
) -> list[LoreChunk]:
    """Split ``text`` into one ``LoreChunk`` per logical H2/H3 section.

    Args:
        text: cleaned, sectioned Markdown (``##`` / ``###`` headings).
        source_url: page the text was extracted from.
        page_title: page name for provenance.
        metadata: page-level properties replicated on every chunk.
        min_length: minimum content length; smaller blocks are absorbed by
            the previous chunk or dropped if the very first section.

    Returns:
        A list of validated ``LoreChunk`` objects.
    """
    sections = _split_sections(text)
    chunks: list[LoreChunk] = []
    for section_title, body in sections:
        body = " ".join(body.split())
        if not body:
            continue
        if len(body) >= min_length:
            chunks.append(
                _build_chunk(
                    source_url, page_title, section_title, body, metadata
                )
            )
            continue
        if chunks:
            merged_text = chunks[-1].content + " " + body
            chunks[-1] = _build_chunk(
                source_url,
                page_title,
                chunks[-1].section_title,
                merged_text,
                metadata,
            )
            logger.info(
                "Merged undersized block '%s' into previous section",
                section_title,
            )
        else:
            logger.info("Dropped undersized lead block (%d chars)", len(body))
    return chunks


def _build_chunk(
    source_url: str,
    page_title: str,
    section_title: str,
    content: str,
    metadata: dict[str, Any] | None,
) -> LoreChunk:
    """Construct and validate a single ``LoreChunk``."""
    return LoreChunk(
        source_url=source_url,
        page_title=page_title,
        section_title=section_title,
        content=content,
        metadata=dict(metadata or {}),
    )


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Slice ``text`` at each Markdown heading, grouping the following body.

    Returns ``[(section_title, body)]`` where the unnamed lead block is
    titled ``INTRODUCTION_TITLE``.
    """
    sections: list[tuple[str, str]] = []
    current_title: str | None = None
    buffer: list[str] = []
    for raw_line in text.splitlines():
        heading = HEADING_RE.match(raw_line.strip())
        if heading:
            _flush_section(sections, current_title, buffer)
            current_title = heading.group(2).strip()
            buffer = []
            continue
        buffer.append(raw_line)
    _flush_section(sections, current_title, buffer)
    return sections


def _flush_section(
    sections: list[tuple[str, str]],
    title: str | None,
    buffer: list[str],
) -> None:
    """Append the pending section when a heading boundary is reached."""
    if buffer:
        sections.append((title or INTRODUCTION_TITLE, "\n".join(buffer)))
