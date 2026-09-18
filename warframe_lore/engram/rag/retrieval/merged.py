"""Merged retriever: compose two ``Retriever`` channels by score.

Runs both searches in parallel, concatenates hits, deduplicates by
passage identity (``page_title`` + ``content``), sorts by score and returns
the global top-k.
"""

from __future__ import annotations

import asyncio

from ....protocols.roleplay import STORY_DOSSIER_PAGE
from .retriever import DossierPage, RAGHit, Retriever


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

    async def dossier(self, subject: str, query_vector: list[float],
                      limit: int = STORY_DOSSIER_PAGE,
                      offset: int = 0,
                      exclude_ids: list[int] | None = None) -> DossierPage:
        gathered: list[RAGHit] = []
        more = False
        for retriever in self.retrievers:
            method = getattr(retriever, "dossier", None)
            if method is None:
                continue
            # The session ban list is forwarded to EVERY sub-retriever: both
            # serial tables restart their BIGSERIAL at 1, so a single mixed
            # ban list can occasionally skip an unseen chunk (lore id 5 vs
            # structured id 5 collide) but can NEVER re-serve a narrated one —
            # a skipped chunk cannot loop a story, only shorten it.
            page = await method(subject, query_vector, limit=limit,
                                offset=offset, exclude_ids=exclude_ids)
            gathered.extend(page.hits)
            more = more or page.more

        merged: dict[tuple[str, str], RAGHit] = {}
        for hit in gathered:
            key = (hit.page_title, hit.content)
            if key not in merged:
                merged[key] = hit
        return DossierPage(hits=list(merged.values()), more=more)
