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
from ...rag import strip_trailing_padding
from ...roleplay import Session
from ...roleplay.turn import TurnPlan
from ..container import Container


async def emit_reply(websocket: WebSocket, text: str) -> None:
    """One deterministic answer: a single token frame, then ``end``."""
    await websocket.send_json(TokenFrame(token=text).model_dump())
    await websocket.send_json(EndFrame(text=text).model_dump())


async def emit_stream(websocket: WebSocket,
                      tokens: AsyncIterator[str]) -> None:
    """Token-by-token emission; ``end`` carries the purged assembled text."""
    parts: list[str] = []
    async for token in tokens:
        parts.append(token)
        await websocket.send_json(TokenFrame(token=token).model_dump())
    await websocket.send_json(
        EndFrame(text=strip_trailing_padding("".join(parts))).model_dump())


def model_turn(container: Container, plan: TurnPlan, payload: dict,
               user_text: str, persona_mode: str,
               session: Session) -> AsyncIterator[str]:
    """The streamed LLM turn: accredited identity + archives + language.

    Only DERIVED values travel from the bot (status label, creator boolean) —
    never a role snowflake, never the creator's Discord ID.  The jealousy
    directive (``creator_mention``) is performed by the model, not scripted.
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
        leverian_warframe=payload.get("leverian_warframe"))


__all__ = ["emit_reply", "emit_stream", "model_turn"]
