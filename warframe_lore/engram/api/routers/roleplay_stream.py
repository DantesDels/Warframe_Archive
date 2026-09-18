"""WebSocket emission of a Roleplay reply (deterministic or streamed).

Single responsibility: turn a reply into frames — one ``token`` plus one ``end``
for a deterministic answer, token by token for the model turn — and purge the
trailing formatting artifacts from the FINAL text.  Story parts get their own
orchestration (:func:`emit_story_turn`) so a window the model narrates nothing
from never reaches the wire nor stops the chain.  The route keeps the
connection handling, :mod:`...roleplay.turn` keeps the decision.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import WebSocket

from ....protocols.roleplay import EndFrame, TokenFrame
from ...rag import RAGContext
from ...roleplay import Session
from ...roleplay.prompt import STORY_COMPLETE_SENTENCE
from ...roleplay.purge import (
    collapse_repeated_closing,
    purge_story_closing,
)
from ...roleplay.turn import TurnPlan, plan_turn
from ..container import Container


async def emit_reply(websocket: WebSocket, text: str) -> None:
    """One deterministic answer: a single token frame, then ``end``."""
    await websocket.send_json(TokenFrame(token=text).model_dump())
    await websocket.send_json(EndFrame(text=text).model_dump())


async def emit_stream(websocket: WebSocket, tokens: AsyncIterator[str],
                      story_more: bool = False) -> str:
    """Token-by-token emission; ``end`` carries the purged assembled text.

    ``story_more`` rides on the terminal frame: the client learns whether the
    subject's dossier still holds unseen fragments behind its cursor.  The
    final text is the canonical end-of-part form (:func:`purge_story_closing`):
    trailing artifacts stripped, trailing closing-line repeats merged into
    ONE.  A part whose whole text degenerated into the closing phrase says
    nothing more: the archivist closing is served and the chain stops
    (``story_more`` forced to False).  Returns the final text.
    """
    parts: list[str] = []
    async for token in tokens:
        parts.append(token)
        await websocket.send_json(TokenFrame(token=token).model_dump())
    text = purge_story_closing("".join(parts))
    if text.strip() == STORY_COMPLETE_SENTENCE:
        story_more = False
    await websocket.send_json(
        EndFrame(text=text, story_more=story_more).model_dump())
    return text


# A part the model answered with ONLY the mandatory closing line (degenerate)
# carries no narration — serving it would show a bare archivist stop while the
# dossier still holds unseen fragments behind the cursor (playtest 00:04).  The
# ``plan_turn`` already grew the session's exclusion memory with the ids of the
# dead window, so re-planning serves the NEXT page: bounded invisible retries
# keep the chain flowing to real material instead of lying about exhaustion.
STORY_RETRY_LIMIT = 2


async def emit_story_turn(websocket: WebSocket, container: Container,
                          payload: dict, user_text: str, persona_mode: str,
                          rag_context: RAGContext,
                          session: Session) -> None:
    """Stream ONE story part, silently skipping windows that narrate nothing.

    The turn is re-planned (and the model called again) only while the current
    window degrades AND the dossier still has unseen fragments
    (``story_more``) — each retry hops past the dead window because the
    exclusion memory advanced at plan time.  The part is emitted — one token
    plus one ``end`` — as soon as it narrates something, or when the dossier
    is truly drained; a genuinely barren dossier ends with the archivist stop
    after ``STORY_RETRY_LIMIT``.
    """
    for attempt in range(STORY_RETRY_LIMIT + 1):
        plan = await plan_turn(container, payload, user_text, persona_mode,
                               rag_context,
                               consumed_chunk_ids=session.consumed_chunk_ids)
        if plan.reply is not None:
            await emit_reply(websocket, plan.reply)
            return
        parts: list[str] = []
        async for token in model_turn(container, plan, payload, user_text,
                                      persona_mode, session):
            parts.append(token)
        text = purge_story_closing("".join(parts))
        dead = text.strip() == STORY_COMPLETE_SENTENCE and plan.story_more
        if dead and attempt < STORY_RETRY_LIMIT:
            continue          # nothing narrated: hop past the dead window
        await websocket.send_json(TokenFrame(token=text).model_dump())
        await websocket.send_json(
            EndFrame(text=text, story_more=plan.story_more and not dead)
            .model_dump())
        return


def model_turn(container: Container, plan: TurnPlan, payload: dict,
               user_text: str, persona_mode: str,
               session: Session) -> AsyncIterator[str]:
    """The streamed LLM turn: accredited identity + archives + language.

    Only DERIVED values travel from the bot (status label, creator boolean) —
    never a role snowflake, never the creator's Discord ID.  The jealousy
    directive (``creator_mention``) is performed by the model, not scripted.
    A ``dossier_offset`` marks a part that continues a running narrative.
    """
    return container.roleplay.stream(
        session, user_text, plan.context_text,
        persona=persona_mode,
        user_name=payload.get("user_name"),
        user_role=payload.get("user_role"),
        role_status=payload.get("role_status"),
        creator=payload.get("creator"),
        creator_mention=payload.get("creator_mention"),
        lang=payload.get("lang"),
        story=bool(payload.get("story")),
        story_lens=payload.get("story_lens"),
        targeted_era=payload.get("targeted_era"),
        leverian_warframe=payload.get("leverian_warframe"),
        story_continuation=bool(payload.get("dossier_offset")),
        story_more=plan.story_more)


__all__ = ["collapse_repeated_closing", "emit_reply", "emit_story_turn",
           "emit_stream", "model_turn"]
