"""Passage deduplication shared by the retrieval channels.

Both serial tables restart their ids at 1, so ``chunk_id`` is not unique
across channels: identity is the passage itself (``page_title`` + content).
"""

from __future__ import annotations

from warframe_lore.engram.rag.retrieval.retriever import RAGHit


def dedupe_first(hits: list[RAGHit]) -> list[RAGHit]:
    """Deduplicate by passage identity; the first occurrence wins."""
    seen: set[tuple[str, str]] = set()
    unique: list[RAGHit] = []
    for hit in hits:
        key = (hit.page_title, hit.content)
        if key not in seen:
            seen.add(key)
            unique.append(hit)
    return unique


__all__ = ["dedupe_first"]
