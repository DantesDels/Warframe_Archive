"""``ChunkManager``: structural chunking (pass 1) + dialogue.

Pass 1 - structural (markdown-aware): the Markdown is split at each
``#`` / ``##`` / ``###`` heading and the heading hierarchy is captured as
metadata.

Pass 2 - recursive with overlap: delegated to the ``splitters`` helpers
(``recursive_character_split``).

Dialogue mode: larger chunks to encompass an entire session, with the
list of speakers in ``metadata["speakers"]``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .splitters import (
    hard_split,
    line_speaker,
    recursive_character_split,
    speakers_metadata,
)
from .patterns import strip_kim_chunk_meta

# Target size (in characters) by default - Pitch Phase 2.5: 1000-1500.
DEFAULT_CHUNK_MAX_CHARACTERS = 1200
# Default overlap - Pitch Phase 2.5: 150-200.
DEFAULT_CHUNK_OVERLAP_CHARACTERS = 175
# Target size for dialogues (whole sessions, preserved context).
DEFAULT_DIALOGUE_CHUNK_MAX_CHARACTERS = 2500
DEFAULT_DIALOGUE_CHUNK_OVERLAP_CHARACTERS = 250

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


@dataclass(frozen=True)
class RAGChunk:
    """A chunk ready for embedding / RAG storage."""

    chunk_index: int
    content_markdown: str
    # JSONB metadata: heading hierarchy (Header 1/2/3) + speakers.
    metadata: dict[str, Any] = field(default_factory=dict)


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
    def split(self, markdown_text: str, is_dialogue: bool = False) -> list[RAGChunk]:
        """Splits Markdown into ordered chunks (0-based chunk_index)."""
        if markdown_text:
            markdown_text = strip_kim_chunk_meta(markdown_text)
        if not markdown_text or not markdown_text.strip():
            return []

        if is_dialogue:
            return self._split_dialogue(markdown_text)

        # Pass 1 -- structural blocks with heading hierarchy.
        structural_blocks = self._split_on_heading_blocks(markdown_text)

        chunks: list[RAGChunk] = []
        for block, headers in structural_blocks:
            block_sections = self._recursive_split(
                block, self.chunk_max_characters,
                self.chunk_overlap_characters)
            for section_text in block_sections:
                if not section_text.strip():
                    continue
                chunks.append(RAGChunk(
                    chunk_index=len(chunks),
                    content_markdown=section_text.strip(),
                    metadata=dict(headers),
                ))
        return chunks

    # ----------------------------------------------------------- pass 1
    def _split_on_heading_blocks(
        self, markdown_text: str,
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

    # ----------------------------------------------------------- pass 2
    def _recursive_split(
        self, text: str, chunk_max_characters: int,
        chunk_overlap_characters: int,
    ) -> list[str]:
        """Recursively splits a text using only the given separators."""
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) <= chunk_max_characters:
            return [text]
        return recursive_character_split(
            text, list(_RECURSIVE_SEPARATORS),
            chunk_max_characters, chunk_overlap_characters)

    # ----------------------------------------------------------- dialogue
    def _split_dialogue(self, markdown_text: str) -> list[RAGChunk]:
        """Splits a dialogue log (KIM / RPG / quests).

        Larger chunks to encompass a whole session.  On a cut, the next
        chunk keeps through ``metadata["speakers"]`` the list of the
        speakers present in the scene.

        Non-dialogue lines (usage note, branches, free text) do not feed
        ``speakers``: only ``> **Name:**`` lines identify a real speaker.
        """
        lines = markdown_text.split("\n")
        chunk_lines: list[str] = []
        per_chunk_speakers: list[str] = []
        chunks: list[RAGChunk] = []

        max_characters = self.dialogue_chunk_max_characters
        overlap_characters = self.dialogue_chunk_overlap_characters

        current_size = 0
        for line in lines:
            if not line.strip():
                continue
            speaker = line_speaker(line)
            line_size = len(line) + 1  # +1 for the line break.

            # A dialogue line that has become too large (rare): hard cut.
            # The current buffer is flushed first, then the line is split
            # into pieces strictly ≤ max_characters (never an oversize
            # chunk, never a duplicate of the whole line), keeping the
            # speaker in the metadata.
            if line_size > max_characters:
                if chunk_lines:
                    chunks.append(RAGChunk(
                        chunk_index=len(chunks),
                        content_markdown="\n".join(chunk_lines),
                        metadata=speakers_metadata(per_chunk_speakers),
                    ))
                long_line_speakers = [speaker] if speaker else []
                for piece in hard_split(
                        line, max_characters, overlap_characters):
                    chunks.append(RAGChunk(
                        chunk_index=len(chunks),
                        content_markdown=piece,
                        metadata=speakers_metadata(long_line_speakers),
                    ))
                chunk_lines = []
                per_chunk_speakers = []
                current_size = 0
                continue

            if current_size + line_size > max_characters and chunk_lines:
                chunks.append(RAGChunk(
                    chunk_index=len(chunks),
                    content_markdown="\n".join(chunk_lines),
                    metadata=speakers_metadata(per_chunk_speakers),
                ))
                # Keeps the speakers of the previous chunk for safety
                # (the interlocutor context must never be lost).
                transition_speakers = list(dict.fromkeys(
                    per_chunk_speakers + ([speaker] if speaker else [])))
                chunk_lines = [line]
                per_chunk_speakers = transition_speakers
                current_size = line_size
                if speaker:
                    per_chunk_speakers.append(speaker)
                continue

            chunk_lines.append(line)
            if speaker:
                per_chunk_speakers.append(speaker)
            current_size += line_size

        if chunk_lines:
            chunks.append(RAGChunk(
                chunk_index=len(chunks),
                content_markdown="\n".join(chunk_lines),
                metadata=speakers_metadata(per_chunk_speakers),
            ))
        return chunks


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