"""WebSocket emission of a Roleplay reply (deterministic or streamed).

Single responsibility: turn a reply into frames — one ``token`` plus one ``end``
for a deterministic answer, token by token for the model turn — and purge the
trailing formatting artifacts from the FINAL text.  The route keeps the
connection handling, :mod:`...roleplay.turn` keeps the decision.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import WebSocket

from ....protocols.roleplay import EndFrame, TokenFrame
from ...roleplay import Session
from ...roleplay.prompt import STORY_COMPLETE_SENTENCE
from ...roleplay.purge import (
    collapse_repeated_closing,
    purge_story_closing,
)
from ...roleplay.turn import TurnPlan
from ..container import Container


async def emit_reply(websocket: WebSocket, text: str) -> None:
    """One deterministic answer: a single token frame, then ``end``."""
    await websocket.send_json(TokenFrame(token=text).model_dump())
    await websocket.send_json(EndFrame(text=text).model_dump())


async def emit_stream(websocket: WebSocket, tokens: AsyncIterator[str],
                      story_more: bool = False) -> None:
    """Token-by-token emission; ``end`` carries the purged assembled text.

    ``story_more`` rides on the terminal frame: the client learns whether the
    subject's dossier still holds unseen fragments behind its cursor.  The
    final text is the canonical end-of-part form (:func:`purge_story_closing`):
    trailing artifacts stripped, trailing closing-line repeats merged into
    ONE.  A part whose whole text degenerated into the closing phrase says
    nothing more: the archivist closing is served and the chain stops
    (``story_more`` forced to False).
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


__all__ = ["collapse_repeated_closing", "emit_reply", "emit_stream",
           "model_turn"]
