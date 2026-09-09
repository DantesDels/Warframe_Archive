"""Route Roleplay KIM (WebSocket) : terminal temps réel.

Gère la connexion temps réel : réception du texte de l'utilisateur, streaming
token par token de la réponse LLM, et historique de session (sliding window).
Une session par connexion WebSocket.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..container import Container
from ...rag import JAILBREAK_REJECT, RAG_ERROR
from ...rag.probes import detect_probe
from ...rag.service import sanitize_query
from ...roleplay import Session

router = APIRouter(tags=["roleplay"])


@router.websocket("/v1/roleplay")
async def roleplay(websocket: WebSocket) -> None:
    await websocket.accept()
    container: Container = websocket.app.state.engram
    # Anti-DDoS : quota de connexions par IP — fermeture 1008 au-delà.
    host = websocket.client.host if websocket.client else "unknown"
    if not container.ws_limiter.allow(host):
        await websocket.send_json(
            {"type": "error",
             "message": "tentative abusive : connexions trop fréquentes"})
        await websocket.close(code=1008, reason="tentative abusive")
        return
    session = Session(session_id=uuid.uuid4().hex)
    # Persona courant de la session : "oracle" (défaut) ou "hostile"
    # (anti-agression).  Le bot bascule sur le mode hostile dès qu'un
    # utilisateur attaque, et revient sur "oracle" après ses excuses.
    persona_mode = "oracle"

    async def send_error(message: str) -> None:
        await websocket.send_json({"type": "error", "message": message})

    try:
        await websocket.send_json(
            {"type": "open", "session_id": session.session_id})
        while True:
            payload = await websocket.receive_json()
            if payload.get("type") == "persona":
                # Bascule de persona (mode hostile / retour oracle) : trame de
                # contrôle — aucune réponse n'est émise côté serveur.
                mode = payload.get("mode")
                if mode in ("oracle", "hostile"):
                    persona_mode = mode
                continue
            if payload.get("type") != "message":
                continue
            # Sanitisation à la frontière : caractères de contrôle et espaces
            # anormaux neutralisés AVANT tout usage (embedding, fenêtre).
            user_text = sanitize_query(str(payload.get("text", "")))
            if not user_text:
                await send_error("message vide ou invalide")
                continue
            # SONDE HOSTILE (injection SQL, escalade de privilèges, mention
            # tiers) : rejet déterministe — la chaîne anti-jailbreak exacte,
            # sans embedding ni appel LLM.
            if detect_probe(user_text):
                await websocket.send_json(
                    {"type": "token", "token": JAILBREAK_REJECT})
                await websocket.send_json(
                    {"type": "end", "text": JAILBREAK_REJECT})
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
                    session, user_text, rag_context, persona=persona_mode):
                response_parts.append(token)
                await websocket.send_json({"type": "token", "token": token})
            await websocket.send_json(
                {"type": "end", "text": "".join(response_parts)})
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 (erreur de flux -> fermeture propre)
        await send_error(f"erreur interne : {exc}")