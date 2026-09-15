"""Dialogue mode — whole-session chunks with ``speakers`` metadata.

Single responsibility: split a dialogue log (KIM / RPG / quests) into
chunks large enough to encompass a whole session, carrying the list of
speakers of the scene in ``metadata["speakers"]``.
"""

from __future__ import annotations

from .model import RAGChunk
from .speakers import line_speaker, speakers_metadata
from .splitters import hard_split


def _split_dialogue_lines(
    markdown_text: str,
    page_title: str,
    chunk_max_characters: int,
    chunk_overlap_characters: int,
) -> list[RAGChunk]:
    """Splits a dialogue log into whole-session chunks.

    Larger chunks to encompass a whole session.  On a cut, the next
    chunk keeps through ``metadata["speakers"]`` the list of the
    speakers present in the scene.

    Non-dialogue lines (usage note, branches, free text) do not feed
    ``speakers``: only ``> **Name:**`` lines identify a real speaker.

    When ``page_title`` is given, it is prepended to each chunk (and
    kept in the metadata) so the vectorized text carries its origin.
    """
    page_prefix = f"Page: {page_title}\n" if page_title else ""

    lines = markdown_text.split("\n")
    chunk_lines: list[str] = []
    per_chunk_speakers: list[str] = []
    chunks: list[RAGChunk] = []

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
        if line_size > chunk_max_characters:
            if chunk_lines:
                chunks.append(RAGChunk(
                    chunk_index=len(chunks),
                    content_markdown=page_prefix + "\n".join(chunk_lines),
                    metadata=speakers_metadata(per_chunk_speakers),
                ))
            long_line_speakers = [speaker] if speaker else []
            for piece in hard_split(
                    line, chunk_max_characters, chunk_overlap_characters):
                chunks.append(RAGChunk(
                    chunk_index=len(chunks),
                    content_markdown=page_prefix + piece,
                    metadata=speakers_metadata(long_line_speakers),
                ))
            chunk_lines = []
            per_chunk_speakers = []
            current_size = 0
            continue

        if current_size + line_size > chunk_max_characters and chunk_lines:
            chunks.append(RAGChunk(
                chunk_index=len(chunks),
                content_markdown=page_prefix + "\n".join(chunk_lines),
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
            content_markdown=page_prefix + "\n".join(chunk_lines),
            metadata=speakers_metadata(per_chunk_speakers),
        ))
    if page_title:
        for chunk in chunks:
            chunk.metadata["page_title"] = page_title
    return chunks
