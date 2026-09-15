"""ENGRAM FastAPI entry point.

Mounts the API, builds the :class:`Container` (services + engine + LLM) in
``app.state.engram`` and exposes the document RAG route as well as the
Roleplay WebSocket terminal. Launch: ``uvicorn warframe_lore.engram.api.main:app``.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from .container import Container
from .routers import document_rag, roleplay, search

# Access audit visible on stderr (server log): INFO level without root
# handler, so that "Audit RAG" lines actually show up.
_engram_log = logging.getLogger("warframe_lore.engram")
if not _engram_log.handlers:
    _engram_log.setLevel(logging.INFO)
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    _engram_log.addHandler(_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = Container()
    app.state.engram = container
    yield
    await container.aclose()


app = FastAPI(title="ENGRAM — Archive KIM",
              version="0.1.0", lifespan=lifespan)

# Local inspection tools (Cephalon UI ``/inspector/`` calls the API from
# http://127.0.0.1:<port>): permissive CORS is acceptable, this server binds
# localhost only and carries no cookie/session.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(document_rag)
app.include_router(roleplay)
app.include_router(search)


@app.middleware("http")
async def ratelimit_rag(request, call_next):
    """Anti-DDoS: ``POST /v1/rag`` capped per IP (429 when quota exceeded).

    Defense is upstream of the LLM — abusive traffic incurs no inference
    cost. The WebSocket terminal shares this philosophy but enforces the
    control in its own route (close code 1008).
    """
    if request.method == "POST" and request.url.path == "/v1/rag":
        limiter = getattr(request.app.state.engram, "rag_limiter", None)
        if limiter is not None:
            host = request.client.host if request.client else "unknown"
            if not limiter.allow(host):
                return Response(
                    content="abusive attempt: rate too high, "
                            "try again later",
                    status_code=429,
                    media_type="text/plain")
    return await call_next(request)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}
