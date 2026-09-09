"""KIM Roleplay route (WebSocket): real-time terminal.

Handles the real-time connection: user text reception, token-by-token LLM
response streaming, and session history (sliding window).
One session per WebSocket connection.
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
    # Anti-DDoS: connection quota per IP — 1008 close beyond it.
    host = websocket.client.host if websocket.client else "unknown"
    if not container.ws_limiter.allow(host):
        await websocket.send_json(
            {"type": "error",
             "message": "abusive attempt: connections too frequent"})
        await websocket.close(code=1008, reason="abusive attempt")
        return
    session = Session(session_id=uuid.uuid4().hex)
    # Current session persona: "oracle" (default) or "hostile"
    # (anti-aggression).  The bot switches to hostile mode as soon as a user
    # attacks, and returns to "oracle" after the apology.
    persona_mode = "oracle"

    async def send_error(message: str) -> None:
        await websocket.send_json({"type": "error", "message": message})

    try:
        await websocket.send_json(
            {"type": "open", "session_id": session.session_id})
        while True:
            payload = await websocket.receive_json()
            if payload.get("type") == "persona":
                # Persona switch (hostile mode / return to oracle): control
                # frame — no reply is emitted server-side.
                mode = payload.get("mode")
                if mode in ("oracle", "hostile"):
                    persona_mode = mode
                continue
            if payload.get("type") != "message":
                continue
            # Frontier sanitisation: control characters and abnormal spacing
            # neutralised BEFORE any use (embedding, window).
            user_text = sanitize_query(str(payload.get("text", "")))
            if not user_text:
                await send_error("empty or invalid message")
                continue
            # HOSTILE PROBE (SQL injection, privilege escalation, third-party
            # mention): deterministic rejection — the exact anti-jailbreak
            # chain, without embedding or LLM call.
            if detect_probe(user_text):
                await websocket.send_json(
                    {"type": "token", "token": JAILBREAK_REJECT})
                await websocket.send_json(
                    {"type": "end", "text": JAILBREAK_REJECT})
                continue
            # "rag" flag: anchor the turn on document passages retrieved by
            # the RAG.  Without a confident passage nor a disambiguation
            # clue, short-circuit: stream the exact error without ever
            # calling the model.
            rag_context = suggestion = None
            if payload.get("rag"):
                rag_context, suggestion = await container.rag.resolve(
                    user_text, user_key=payload.get("user_id"))
            if not rag_context and suggestion is None and payload.get("rag"):
                await websocket.send_json({"type": "token", "token": RAG_ERROR})
                await websocket.send_json({"type": "end", "text": RAG_ERROR})
                continue
            # Token-by-token streaming; accumulate to close the turn.  The
            # Discord identity (display name + galaxy rank) feeds the
            # hierarchical-immunity directive in the system prompt.
            response_parts: list[str] = []
            async for token in container.roleplay.stream(
                    session, user_text, rag_context, persona=persona_mode,
                    user_name=payload.get("user_name"),
                    user_role=payload.get("user_role")):
                response_parts.append(token)
                await websocket.send_json({"type": "token", "token": token})
            await websocket.send_json(
                {"type": "end", "text": "".join(response_parts)})
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 (stream error -> clean close)
        await send_error(f"internal error: {exc}")