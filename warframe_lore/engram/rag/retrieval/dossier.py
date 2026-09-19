"""Lore dossier: the subject's own pages in narrative reading order.

Targeted-story anchoring (playtest "l'histoire d'Eleanor"): the pure semantic
search ranks first-person KIM dialogues above the subject's narrative page —
the Eleanor Background section landed at rank ~16, far under the top_k=3, so
the story corpus carried no actual story.  The dossier walks the subject's
OWN pages in READING order — the exact biography page (``Eleanor``, or
``Leticia`` when the key is the alias ``lettie``) first, then its section
pages (``Eleanor/Quotes``), then TITLE-matching pages, then content-only
mentions — so a targeted story is grounded on the narrative itself.  Each
chunk keeps its cosine score: the relevance floor still drops off-story
sections.  ``offset`` is a continuation marker kept for the wire contract
(the pipeline always pages from ``0``); ``exclude_ids`` is the real cursor:
the chunks the session already narrated are banned in SQL.  One chunk is
fetched beyond the window to know whether anything is left (no COUNT query).
"""

from __future__ import annotations

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from ....db import LoreChunk, WikiPage
from ....protocols.roleplay import STORY_DOSSIER_PAGE
from ..query.aliases import dossier_title_terms
from .hnsw import set_hnsw_ef_search
from .retriever import DossierPage, RAGHit

# Dossier retrieval cap: enough narrative chunks to fill ``max_context_chars``
# (~4500 chars) without dragging in the whole subject page family.  ONE page is
# also the cursor step of a continuation, shared by both sides of the wire.
DOSSIER_LIMIT = STORY_DOSSIER_PAGE


def lore_dossier_statement(subject: str, query_vector: list[float],
                           limit: int = DOSSIER_LIMIT, offset: int = 0,
                           exclude_ids: list[int] | None = None):
    """SELECT statement: subject chunks in narrative reading order.

    Tier 0 = the exact biography page (``Eleanor`` — and its canonical alias
    ``Leticia`` when the subject KEY is the nickname ``lettie``), tier 1 = its
    section pages (``Eleanor/Quotes``), tier 2 = every page whose TITLE
    contains a term, tier 3 = content-only mentions.  The French mirror of the
    exact page (``Eleanor (fr)``) shares tier 0: its namespaced id sorts right
    after the English bio, so both languages ground the story while English
    stays first.  Reading order (``chunk_index``) keeps the narrative
    sequence; the cosine distance is still computed so the relevance floor
    applies.  ``exclude_ids`` bans the chunks the session already narrated
    (the ONLY pagination): the server never trusts a client cursor.
    """
    terms = dossier_title_terms(subject)
    distance = LoreChunk.embedding.cosine_distance(
        query_vector).label("dist")
    tier = case(
        (or_(*[WikiPage.page_title.ilike(term) for term in terms]), 0),
        (or_(*[WikiPage.page_title.ilike(f"{term} (fr)")
               for term in terms]), 0),
        (or_(*[WikiPage.page_title.ilike(f"{term}/%")
               for term in terms]), 1),
        (or_(*[WikiPage.page_title.ilike(f"%{term}%")
               for term in terms]), 2),
        else_=3,
    )
    stmt = (
        select(LoreChunk, distance)
        .options(selectinload(LoreChunk.wiki_page))
        .join(WikiPage, LoreChunk.wiki_page_id == WikiPage.page_id)
        .where(
            LoreChunk.embedding.is_not(None),
            or_(
                *[WikiPage.page_title.ilike(f"%{term}%")
                  for term in terms],
                *[LoreChunk.content_markdown.ilike(f"%{term}%")
                  for term in terms],
            ),
        )
    )

    # Exclusion filter: the chunks the session already narrated.
    if exclude_ids:
        stmt = stmt.where(LoreChunk.id.notin_(exclude_ids))

    return (
        stmt.order_by(tier, WikiPage.page_id, LoreChunk.chunk_index)
        .limit(limit)
        .offset(offset)
    )


async def fetch_dossier_page(sessions: async_sessionmaker,
                             ef_search: int, subject: str,
                             query_vector: list[float],
                             limit: int = DOSSIER_LIMIT, offset: int = 0,
                             exclude_ids: list[int] | None = None) -> DossierPage:
    """One page of the subject's dossier, story-first.

    Runs :func:`lore_dossier_statement` on the caller's session maker with the
    HNSW pool widened, then shapes the rows into a :class:`DossierPage` — one
    chunk beyond the window tells whether anything is left (``more``).
    """
    # +1 lookahead: the page is returned with ``more`` when a chunk stands
    # beyond the window.
    statement = lore_dossier_statement(
        subject, query_vector, limit + 1, offset, exclude_ids)

    hits: list[RAGHit] = []
    async with sessions() as session:
        await set_hnsw_ef_search(session, ef_search)
        rows = (await session.execute(statement)).all()
        for chunk, dist in rows:
            hits.append(RAGHit(
                chunk_id=chunk.id,
                page_title=chunk.wiki_page.page_title,
                content=chunk.content_markdown,
                score=1.0 - float(dist),
            ))
    return DossierPage(hits=hits[:limit], more=len(hits) > limit)


__all__ = ["DOSSIER_LIMIT", "fetch_dossier_page", "lore_dossier_statement"]
