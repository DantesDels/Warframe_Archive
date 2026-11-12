"""Structural (markdown-aware) sectioning helpers — pass 1 & 2.

Single responsibility: split Markdown at each ``#``/``##``/``###`` heading
and capture the heading hierarchy as metadata, then run the recursive
character split (with overlap) on each block.
"""

from __future__ import annotations

import re

from .splitters import recursive_character_split

_HEADING_TITLE_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")

# Separators for the recursive pass, in order of preference.
_RECURSIVE_SEPARATORS = [
    "\n\n",   # paragraph boundary (highest priority).
    "\n",     # line boundary.
    ". ",     # sentence boundary.
    "! ",
    "? ",
    " ",      # last resort: word.
]


def _strip_heading_lines(text: str) -> str:
    """Drops the markdown heading lines of a structural block.

    The heading context is carried by the ``"Section: Y"`` part of the
    context prefix; keeping the ``## Y`` line would duplicate it in the
    vectorized text.
    """
    lines = [line for line in text.split("\n")
             if not _HEADING_TITLE_PATTERN.match(line.strip())]
    return "\n".join(lines).strip()


def _section_chain(headers: dict[str, str]) -> str:
    """Human-readable section label from the heading hierarchy.

    A block nested under ``## Identité passée`` / ``### Ordan Karris``
    yields ``"Identité passée > Ordan Karris"``.  The top-level ``#``
    heading is skipped: it names the page itself, already carried by the
    ``"Page: X"`` part of the context prefix.
    """
    titles = [headers[f"Header {level}"]
              for level in range(2, 7)
              if headers.get(f"Header {level}")]
    return " > ".join(title for title in titles if title)


def _context_prefix(page_title: str, section: str) -> str:
    """Context prefix for semantic retrieval.

    Output: ``"Page: X | Section: Y - "`` (or ``"Page: X - "`` when there
    is no section to name).
    """
    prefix = f"Page: {page_title}"
    if section:
        prefix += f" | Section: {section}"
    return prefix + " - "


def _split_on_heading_blocks(
    markdown_text: str,
) -> list[tuple[str, dict[str, str]]]:
    """Splits into blocks delimited by headings, with hierarchy.

    Returns ``[(text, {header_level: title, ...}), ...]``.
    """
    blocks: list[tuple[str, dict[str, str]]] = []
    current_lines: list[str] = []
    current_headers: dict[str, str] = {}

    for line in markdown_text.split("\n"):
        heading_match = _HEADING_TITLE_PATTERN.match(line.strip())
        if heading_match is not None:
            # Ends the current block (if it has non-heading content).
            if current_lines:
                blocks.append(("\n".join(current_lines),
                               dict(current_headers)))
            # Grabs the new hierarchy: the current heading overrides
            # its level and any deeper sub-levels are dropped.
            heading_level = len(heading_match.group(1))
            heading_title = heading_match.group(2).strip()
            new_headers = dict(current_headers)
            new_headers[f"Header {heading_level}"] = heading_title
            # Removes the sub-levels that came AFTER this heading
            # (e.g. a '###' before a new '##' must be forgotten).
            for level in range(heading_level + 1, 7):
                new_headers.pop(f"Header {level}", None)
            current_headers = new_headers
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        blocks.append(("\n".join(current_lines), dict(current_headers)))
    return blocks


def _recursive_split(
    text: str, chunk_max_characters: int,
    chunk_overlap_characters: int,
) -> list[str]:
    """Recursively splits a text using only the given separators."""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) <= chunk_max_characters:
        return [text]
    return recursive_character_split(
        text, list(_RECURSIVE_SEPARATORS),
        chunk_max_characters, chunk_overlap_characters)
