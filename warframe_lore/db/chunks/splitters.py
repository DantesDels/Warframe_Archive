"""Chunking helpers (pass 2): recursive split, overlap, hard cut.

Single responsibility: the pure text-splitting machinery (no state), reused by
the structural ``ChunkManager`` and by the dialogue mode.  Speaker detection
lives in :mod:`speakers`.
"""

from __future__ import annotations


def recursive_character_split(
    text: str,
    separators: list[str],
    chunk_max_characters: int,
    chunk_overlap_characters: int,
) -> list[str]:
    """Recursive splitter (the ``RecursiveCharacterTextSplitter`` equivalent).

    1. It splits on the first separator found then *merges* the consecutive
       pieces until approaching ``chunk_max_characters``;
    2. Any piece still too large is re-processed with the next separator
       (recursive);
    3. Overlap is then applied: each chunk carries the tail of the previous
       one to preserve context.
    """
    if not separators:
        return hard_split(text, chunk_max_characters, chunk_overlap_characters)

    separator = separators[0]
    remaining_separators = separators[1:]

    pieces = text.split(separator)
    if len(pieces) == 1:
        # The current separator is not in the text: try the next one.
        return recursive_character_split(
            text, remaining_separators,
            chunk_max_characters, chunk_overlap_characters)

    # Merges the pieces into chunks close to the target size.
    merged_chunks = _merge_pieces(
        pieces, separator, chunk_max_characters, chunk_overlap_characters)

    final_chunks: list[str] = []
    for chunk in merged_chunks:
        if len(chunk) <= chunk_max_characters:
            final_chunks.append(chunk)
        elif remaining_separators:
            final_chunks.extend(recursive_character_split(
                chunk, remaining_separators,
                chunk_max_characters, chunk_overlap_characters))
        else:
            # No more separators available: hard cut with overlap.
            final_chunks.extend(hard_split(
                chunk, chunk_max_characters, chunk_overlap_characters))

    return _apply_overlap(final_chunks, chunk_max_characters,
                          chunk_overlap_characters)


def _merge_pieces(
    pieces: list[str],
    separator: str,
    chunk_max_characters: int,
    chunk_overlap_characters: int,
) -> list[str]:
    """Assembles consecutive pieces into chunks close to the target.

    The separator is re-appended after each piece (except the last one) so
    no information is lost.
    """
    merged_chunks: list[str] = []
    current_piece = ""

    for index, piece in enumerate(pieces):
        separator_after = separator if index < len(pieces) - 1 else ""
        piece_with_separator = piece + separator_after
        candidate_length = len(current_piece) + len(piece_with_separator)

        if current_piece and candidate_length > chunk_max_characters:
            if current_piece.strip():
                merged_chunks.append(current_piece)
            current_piece = piece_with_separator
        else:
            current_piece += piece_with_separator

    if current_piece.strip():
        merged_chunks.append(current_piece)
    return merged_chunks


def _apply_overlap(
    chunks: list[str],
    chunk_max_characters: int,
    chunk_overlap_characters: int,
) -> list[str]:
    """Prefixes each chunk (except the first) with the previous one's tail.

    Guarantees context continuity between consecutive chunks, without
    duplicating when the overlap is already present, and without ever
    exceeding ``chunk_max_characters`` (the added context is bounded).
    """
    if len(chunks) <= 1 or chunk_overlap_characters <= 0:
        return chunks

    result: list[str] = []
    for index, chunk in enumerate(chunks):
        if index == 0:
            result.append(chunk)
            continue
        previous_tail = chunks[index - 1][-chunk_overlap_characters:]
        if chunk.startswith(previous_tail):
            result.append(chunk)
            continue
        # Bounds the prefixed tail to stay ≤ chunk_max_characters.
        room_for_overlap = max(0, chunk_max_characters - len(chunk))
        bounded_tail = previous_tail[-room_for_overlap:] if room_for_overlap else ""
        result.append(bounded_tail + chunk)
    return result


def hard_split(text: str, chunk_max_characters: int,
               chunk_overlap_characters: int) -> list[str]:
    """Splits a very long text into fixed-size pieces + overlap."""
    step_size = chunk_max_characters - chunk_overlap_characters
    if step_size <= 0:
        step_size = chunk_max_characters
    pieces: list[str] = []
    start_index = 0
    while start_index < len(text):
        end_index = start_index + chunk_max_characters
        pieces.append(text[start_index:end_index])
        start_index += step_size
    return pieces


__all__ = ["hard_split", "recursive_character_split"]
