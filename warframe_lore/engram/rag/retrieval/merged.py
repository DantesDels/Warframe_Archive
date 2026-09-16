"""Merged retriever: compose two ``Retriever`` channels by score.

Runs both searches in parallel, concatenates hits, deduplicates by
``chunk_id``, sorts by score and returns the global top-k.
"""

from __future__ import annotations

import asyncio

from .retriever import RAGHit, Retriever


class MergedRetriever(Retriever):
    """Wraps multiple retrievers, fuses results by cosine score."""

    def __init__(self, *retrievers: Retriever, top_k: int = 6) -> None:
        self.retrievers = list(retrievers)
        self.top_k = top_k

    async def search(self, query_vector: list[float]) -> list[RAGHit]:
        all_hits = await asyncio.gather(
            *(r.search(query_vector) for r in self.retrievers)
        )
        # Both serial tables (lore_chunks, structured_chunks) restart their
        # BIGSERIAL at 1: chunk_id is NOT unique across channels, so the
        # dedup keys on the passage identity (page_title + content).
        merged: dict[tuple[str, str], RAGHit] = {}
        for hits in all_hits:
            for hit in hits:
                key = (hit.page_title, hit.content)
                if key not in merged or hit.score > merged[key].score:
                    merged[key] = hit
        ranked = sorted(merged.values(), key=lambda h: h.score, reverse=True)
        return ranked[: self.top_k]

    async def suggest_title(self, question: str) -> str | None:
        """Delegate to the first retriever that returns a suggestion."""
        for retriever in self.retrievers:
            suggest = getattr(retriever, "suggest_title", None)
            if suggest is not None:
                result = await suggest(question)
                if result is not None:
                    return result
        return None

    async def dossier(self, subject: str,
                      query_vector: list[float]) -> list[RAGHit]:
        """Narrative-first page dossier across sub-retrievers that support it.

        Only the channels owning a ``dossier`` method contribute (CosinusSearch
        for lore_chunks).  The sub-retriever order preserves the biography
        page first; the dedup policy matches :meth:`search`.
        """
        gathered: list[RAGHit] = []
        for retriever in self.retrievers:
            method = getattr(retriever, "dossier", None)
            if method is not None:
                gathered.extend(await method(subject, query_vector))
        merged: dict[tuple[str, str], RAGHit] = {}
        for hit in gathered:
            key = (hit.page_title, hit.content)
            if key not in merged:
                merged[key] = hit
        return list(merged.values())
