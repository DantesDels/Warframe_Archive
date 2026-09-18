"""KIM Roleplay route (WebSocket): real-time terminal.

Transport only: accept, enforce the per-IP quota, dispatch frames, emit replies.
The turn decision lives in :mod:`warframe_lore.engram.roleplay.turn`, the emission
in :mod:`roleplay_stream`; one session per user, RAG anaphora per connection.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ....protocols.roleplay import (
    FRAME_COMMENT,
    FRAME_MESSAGE,
    FRAME_PERSONA,
    FRAME_RESET,
    PERSONA_MODES,
    PERSONA_ORACLE,
    CommentFrame,
    ErrorFrame,
    OpenFrame,
)
from ...rag import RAGContext, RAGContextFactory
from ...rag.query.query_guard import sanitize_query
from ...roleplay import Session
from ...roleplay.replies import member_comment
from ...roleplay.turn import plan_turn
from ..container import Container
from .roleplay_stream import (
    emit_reply,
    emit_story_turn,
    emit_stream,
    model_turn,
)

router = APIRouter(tags=["roleplay"])


@router.websocket("/v1/roleplay")
async def roleplay(websocket: WebSocket) -> None:
    await websocket.accept()
    container: Container = websocket.app.state.engram
    # Anti-DDoS: connection quota per IP — 1008 close beyond it.
    host = websocket.client.host if websocket.client else "unknown"
    if not container.ws_limiter.allow(host):
        await websocket.send_json(ErrorFrame(
            message="abusive attempt: connections too frequent").model_dump())
        await websocket.close(code=1008, reason="abusive attempt")
        return
    session = Session(session_id=uuid.uuid4().hex)
    # "oracle" (default) or "hostile": an attacker's session is flipped, then back.
    persona_mode = PERSONA_ORACLE
    rag_context: RAGContext = RAGContext()

    def active_session(user_id) -> Session:
        """PER-USER short-term memory; anonymous clients keep the fallback."""
        if user_id is None:
            return session
        return container.memory.get(user_id, persona_mode)

    async def send_error(message: str) -> None:
        await websocket.send_json(ErrorFrame(message=message).model_dump())

    try:
        await websocket.send_json(
            OpenFrame(session_id=session.session_id).model_dump())
        while True:
            payload = await websocket.receive_json()
            kind = payload.get("type")
            if kind == FRAME_PERSONA:
                mode = payload.get("mode")
                if mode in PERSONA_MODES:
                    persona_mode = mode
                continue                    # control frame: no reply emitted
            if kind == FRAME_RESET:
                container.memory.forget(payload.get("user_id"))
                continue                    # Discord ``!reset``
            if kind == FRAME_COMMENT:
                text = await member_comment(container, payload)
                await websocket.send_json(CommentFrame(text=text).model_dump())
                continue                    # one-shot, non-streamed
            if kind != FRAME_MESSAGE:
                continue
            # Frontier sanitisation: control chars neutralised BEFORE any use.
            user_text = sanitize_query(str(payload.get("text", "")))
            if not user_text:
                await send_error("empty or invalid message")
                continue
            user_id = payload.get("user_id")
            if user_id is not None and rag_context.user_key != user_id:
                rag_context = RAGContextFactory.create(user_key=user_id)
            session = active_session(user_id)
            # The SESSION carries the exclusion memory (``consumed_chunk_ids``)
            # that makes a continuation serve unseen fragments instead of
            # repeating the previous part: the router hands it to the turn.
            plan = await plan_turn(container, payload, user_text, persona_mode,
                                   rag_context,
                                   consumed_chunk_ids=session.consumed_chunk_ids)
            if plan.reply is not None:
                await emit_reply(websocket, plan.reply)
                continue
            if payload.get("story"):
                # Story parts hop past windows the model narrates nothing from
                # (see ``emit_story_turn``): a dead window is left behind
                # instead of stopping the chain with a false exhaustion.
                await emit_story_turn(websocket, container, payload,
                                      user_text, persona_mode, rag_context,
                                      session)
                continue
            await emit_stream(websocket, model_turn(
                container, plan, payload, user_text, persona_mode, session),
                story_more=plan.story_more)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 (stream error -> clean close)
        await send_error(f"internal error: {exc}")
