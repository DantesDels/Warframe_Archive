"""KIM Roleplay route (WebSocket): real-time terminal.

Handles the real-time connection: user text reception, token-by-token LLM
response streaming, and session history (sliding window).
One session per user (``message.author.id``, plus persona slice) via the
shared :class:`UserMemoryStore` — memory, not stateless channels; anonymous
clients keep a per-connection fallback session.

State isolation: conversational RAG memory (anaphora) lives in ONE
:class:`RAGContext` per connection — created here, never on the shared
service. A user switch (different ``user_id``) clears the context;
connection close garbage-collects it (one WS connection == one user).
Trailing formatting artifacts (lone ``*`` / ``-`` / whitespace) are
stripped from the FINAL ``end`` frame just before emission.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..container import Container
from ...rag import JAILBREAK_REJECT, RAG_ERROR
from ...rag.context import RAGContext, RAGContextFactory
from ...rag.probes import detect_probe, is_identity_question, is_self_reflection
from ...roleplay.identity import (external_organic_reply, identity_reply,
                                  member_roster_reply)
from ...rag.sanitize import strip_trailing_padding
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
    # Per-connection ephemeral RAG memory (anaphora). Isolated per user: a
    # different ``user_id`` on the same connection clears the context.
    rag_context: RAGContext = RAGContext()

    def active_session(user_id) -> Session:
        # PER-USER short-term memory (mission-6): keyed by the Discord
        # ``message.author.id`` (+ persona slice).  Anonymous clients keep
        # the per-connection fallback session.
        if user_id is None:
            return session
        return container.memory.get(user_id, persona_mode)

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
            if payload.get("type") == "reset":
                # Wipe the user's short-term memory (Discord ``!reset``).
                container.memory.forget(payload.get("user_id"))
                continue
            if payload.get("type") != "message":
                continue
            # Frontier sanitisation: control characters and abnormal spacing
            # neutralised BEFORE any use (embedding, window).
            user_text = sanitize_query(str(payload.get("text", "")))
            if not user_text:
                await send_error("empty or invalid message")
                continue
            # Isolate the RAG context per user: a new speaker on the same
            # connection must not inherit the previous user's memory.
            user_id = payload.get("user_id")
            if user_id is not None and rag_context.user_key != user_id:
                rag_context = RAGContextFactory.create(user_key=user_id)
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
            # calling the model.  Introspection turns (the Oracle itself /
            # its creator) never ground on the archives: the consciousness
            # exception (BLOC 2 / auth banner) applies instead — the
            # short-circuit must never answer 'Données insuffisantes' there.
            context_text = suggestion = None
            want_rag = bool(payload.get("rag")) \
                and not is_self_reflection(user_text)
            if want_rag:
                context_text, suggestion = await container.rag.resolve(
                    user_text, context=rag_context)
            if not context_text and suggestion is None and want_rag:
                await websocket.send_json({"type": "token", "token": RAG_ERROR})
                await websocket.send_json({"type": "end", "text": RAG_ERROR})
                continue
            # Questions about a GUILD MEMBER (external organic, "Qui est Aze
            # ?"): the bot resolved the speaker's pseudo against the member
            # list (exact or prefix abbreviation) and sent ``member_name``.
            # Deterministic protocol — the persona's GESTION DES ORGANIQUES
            # EXTERNES : factual, no affection, cold disdain. NEVER the lore
            # archives ("Données insuffisantes" was the playtest bug) and
            # never the RAG that would hallucinate the member as lore.
            member_name = payload.get("member_name")
            if persona_mode == "oracle" and member_name:
                member_roles = payload.get("member_roles")
                member_affiliated = payload.get("member_affiliated")
                if member_affiliated is None:
                    member_affiliated = True
                reluctant = bool(payload.get("reluctant"))
                creator = bool(payload.get("creator"))
                if member_roles is not None:
                    organic_answer = member_roster_reply(
                        str(member_name), list(member_roles),
                        affiliated=bool(member_affiliated),
                        creator=creator, reluctant=reluctant)
                else:
                    organic_answer = external_organic_reply(
                        str(member_name), creator=creator,
                        affiliated=bool(member_affiliated),
                        reluctant=reluctant)
                await websocket.send_json(
                    {"type": "token", "token": organic_answer})
                await websocket.send_json(
                    {"type": "end", "text": organic_answer})
                continue
            # Speaker-identity questions ("qui suis-je ?", "quel est mon rôle
            # ?"): DETERMINISTIC answer from the accredited data (BLOC 2
            # identity).  The devotion persona (CAS A) keeps self-introducing
            # instead of presenting the speaker — the LLM is never called
            # here.  Anonymous clients (no identity payload) fall back to the
            # LLM turn below; the hostile persona keeps its insistence (the
            # attacker must apologise, whatever the question).
            identity_answer = None
            if persona_mode == "oracle" and is_identity_question(user_text):
                identity_answer = identity_reply(
                    user_name=payload.get("user_name"),
                    user_role=payload.get("user_role"),
                    user_roles=payload.get("user_roles"),
                    role_status=payload.get("role_status"),
                    creator=bool(payload.get("creator")))
            if identity_answer:
                await websocket.send_json(
                    {"type": "token", "token": identity_answer})
                await websocket.send_json(
                    {"type": "end", "text": identity_answer})
                continue
            # A NON-CONCEPTOR has just cited the Concepteur's pseudonym (any
            # spelling/casing).  Persona-driven jealousy: no RAG (the archives
            # must not bury the rage under "Données insuffisantes"), no
            # deterministic short-circuit — the LLM improvises the possessive
            # fury guided by the directive injected in ``stream``.
            creator_mention = payload.get("creator_mention")
            # Token-by-token streaming; accumulate to close the turn.  The
            # Discord identity (display name + galaxy rank) feeds the
            # hierarchical-immunity directive in the system prompt; the
            # boolean ``creator`` (derived by the bot, never the raw ID)
            # selects the persona banner; ``role_status`` (bot-side role
            # accreditation, mission-8) drives the BLOC 2 status.  Session =
            # the per-user memory cell.
            response_parts: list[str] = []
            async for token in container.roleplay.stream(
                    active_session(user_id), user_text, context_text,
                    persona=persona_mode,
                    user_name=payload.get("user_name"),
                    user_role=payload.get("user_role"),
                    role_status=payload.get("role_status"),
                    creator=payload.get("creator"),
                    creator_mention=creator_mention):
                response_parts.append(token)
                await websocket.send_json({"type": "token", "token": token})
            # Final emission: strip trailing formatting artifacts (lone ``*``
            # / ``-`` / whitespace) from the FINAL assembled text.
            await websocket.send_json(
                {"type": "end",
                 "text": strip_trailing_padding("".join(response_parts))})
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 (stream error -> clean close)
        await send_error(f"internal error: {exc}")