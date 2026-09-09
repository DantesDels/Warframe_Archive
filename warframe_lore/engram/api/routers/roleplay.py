"""Route Roleplay KIM (WebSocket) : terminal temps réel.

Gère la connexion temps réel : réception du texte de l'utilisateur, streaming
token par token de la réponse LLM, et historique de session (sliding window).
Une session par connexion WebSocket.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..container import Container
from ...rag import RAG_ERROR
from ...roleplay import Session

router = APIRouter(tags=["roleplay"])


@router.websocket("/v1/roleplay")
async def roleplay(websocket: WebSocket) -> None:
    await websocket.accept()
    container: Container = websocket.app.state.engram
    session = Session(session_id=uuid.uuid4().hex)

    async def send_error(message: str) -> None:
        await websocket.send_json({"type": "error", "message": message})

    try:
        await websocket.send_json(
            {"type": "open", "session_id": session.session_id})
        while True:
            payload = await websocket.receive_json()
            if payload.get("type") != "message":
                continue
            user_text = str(payload.get("text", "")).strip()
            if not user_text:
                await send_error("message vide ignoré")
                continue
            # Flag "rag" : ancrer le tour sur des passages documentaires
            # récupérés par le RAG.  Sans passage de confiance ni piste de
            # désambiguïsation, short-circuit : on streame l'erreur exacte
            # sans jamais appeler le modèle.
            rag_context = suggestion = None
            if payload.get("rag"):
                rag_context, suggestion = await container.rag.resolve(user_text)
            if not rag_context and suggestion is None and payload.get("rag"):
                await websocket.send_json({"type": "token", "token": RAG_ERROR})
                await websocket.send_json({"type": "end", "text": RAG_ERROR})
                continue
            # Streaming token par token ; on accumule pour clôturer le tour.
            response_parts: list[str] = []
            async for token in container.roleplay.stream(
                    session, user_text, rag_context):
                response_parts.append(token)
                await websocket.send_json({"type": "token", "token": token})
            await websocket.send_json(
                {"type": "end", "text": "".join(response_parts)})
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 (erreur de flux -> fermeture propre)
        await send_error(f"erreur interne : {exc}")