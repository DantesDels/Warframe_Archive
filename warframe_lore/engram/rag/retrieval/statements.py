"""SQL statements of the two hybrid retrieval channels.

Single responsibility: the pgvector cosine query and the PostgreSQL French
full-text query (``websearch_to_tsquery`` + ``ts_rank_cd`` + ``ts_headline``).
The channels are intentionally NOT fused in SQL — each keeps its own retrieval
ordering (HNSW for cosine, ``ts_rank`` for FTS) and the merge happens in Python,
so both raw scores stay visible.
"""

from __future__ import annotations

from sqlalchemy import func, select

from ....db import LoreChunk, WikiPage
from .scoring import FTS_CONFIG, FTS_HEADLINE_OPTIONS


def cosine_statement(query_vector: list[float], candidates: int):
    """Top candidates by cosine similarity.

    No hard floor on purpose: the inspector must see weak hits too — relevance
    thresholds belong to :class:`RAGService`, not to the SQL.
    """
    distance = LoreChunk.embedding.cosine_distance(query_vector)
    return (
        select(LoreChunk, (1.0 - distance).label("cos"), WikiPage.page_title)
        .join(WikiPage, LoreChunk.wiki_page_id == WikiPage.page_id)
        .where(LoreChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(candidates)
    )


def fts_statement(query: str, candidates: int):
    """Top candidates by French full-text rank, with the matching snippet."""
    tsvector = func.to_tsvector(FTS_CONFIG, LoreChunk.content_markdown)
    tsquery = func.websearch_to_tsquery(FTS_CONFIG, query)
    return (
        select(LoreChunk,
               func.ts_rank_cd(tsvector, tsquery, 32).label("ts"),
               func.ts_headline(FTS_CONFIG, LoreChunk.content_markdown,
                                tsquery, FTS_HEADLINE_OPTIONS)
               .label("headline"),
               WikiPage.page_title)
        .join(WikiPage, LoreChunk.wiki_page_id == WikiPage.page_id)
        .where(tsvector.op("@@")(tsquery))
        .order_by(func.ts_rank_cd(tsvector, tsquery, 32).desc())
        .limit(candidates)
    )


__all__ = ["cosine_statement", "fts_statement"]
