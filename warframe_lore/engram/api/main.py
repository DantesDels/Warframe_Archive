"""Point d'entrée FastAPI d'ENGRAM.

Monte l'API, construit le :class:`Container` (services + engine + LLM) dans
``app.state.engram`` et expose la route RAG documentaire ainsi que le
terminal Roleplay WebSocket.  Lancement : ``uvicorn warframe_lore.engram.api.main:app``.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .container import Container
from .routers import document_rag, roleplay

# Audit d'accès visible sur stderr (log serveur) : niveau INFO sans handler
# racine, pour que les lignes "Audit RAG" ressortent effectivement.
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

app.include_router(document_rag)
app.include_router(roleplay)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}