"""Hybrid search route (RAG Inspector backend).

``GET /v1/search``: chunk-level hybrid search (pgvector cosine + PostgreSQL
full-text). Transport only: the route delegates to :class:`HybridSearch`
injected via the application ``Container``. The optional ``debug=true``
flag reassembles the EXACT prompt payload a RAG call would send to the LLM
(system template + concatenated chunks) for context-bleed audit.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from ..schemas import SearchDebug, SearchHit, SearchResponse
from ...rag import RAGHit
from ...rag.hybrid import HybridSearch

router = APIRouter(prefix="/v1/search", tags=["search"])


def _search(request: Request) -> HybridSearch:
    return request.app.state.engram.search


@router.get("", response_model=SearchResponse)
async def hybrid_search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(12, ge=1, le=50),
    debug: bool = Query(False, description="Annexe le payload LLM exact"),
):
    result = await _search(request).search(q, limit=limit)
    hits = [
        SearchHit(
            chunk_id=h.chunk_id,
            page_title=h.page_title,
            section=h.section,
            content=h.content,
            metadata=h.chunk_metadata,
            cosine_score=h.cosine_score,
            ts_score=h.ts_score,
            score=h.score,
            headline=h.headline,
        )
        for h in result.hits
    ]
    payload = None
    if debug:
        prompt = request.app.state.engram.rag.prompt_builder.build(
            result.query,
            [RAGHit(hit.chunk_id, hit.page_title, hit.content, hit.score)
             for hit in result.hits],
            alias_note=result.alias_note)
        payload = SearchDebug(
            system=prompt.system,
            context=prompt.context,
            user_question=prompt.user_question,
            messages=prompt.to_messages(),
        )
    return SearchResponse(
        query=result.query,
        search_question=result.search_question,
        alias_note=result.alias_note,
        alias_active=result.alias_active,
        canonical=result.canonical,
        highlight_terms=result.terms,
        hits=hits,
        debug=payload,
    )