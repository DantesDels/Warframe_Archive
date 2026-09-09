"""Document RAG route (HTTP POST).

Purely transport layer (S + D principle): no business logic or data access
here — the route delegates to :class:`RAGService` injected via the
application ``Container`` (``app.state.engram``).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from ..schemas import RAGRequest, RAGResponse, SourceDocument
from ...rag import RAGService

router = APIRouter(prefix="/v1/rag", tags=["rag"])


def _rag(request: Request) -> RAGService:
    return request.app.state.engram.rag


@router.post("")
async def document_rag(req: RAGRequest, request: Request):
    service = _rag(request)
    if req.stream:
        return StreamingResponse(service.stream_answer(req.question),
                                 media_type="text/plain")
    answer, hits = await service.answer_with_sources(req.question)
    sources = [SourceDocument(h.page_title, h.content, h.score)
               for h in hits]
    return RAGResponse(answer=answer, sources=sources)