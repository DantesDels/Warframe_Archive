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
from ...roleplay.prompt import (
    STORY_COMPLETE_SENTENCE,
    STORY_PAGINATION_SENTENCE,
)
from ...roleplay.turn import TurnPlan
from ..container import Container


async def emit_reply(websocket: WebSocket, text: str) -> None:
    """One deterministic answer: a single token frame, then ``end``."""
    await websocket.send_json(TokenFrame(token=text).model_dump())
    await websocket.send_json(EndFrame(text=text).model_dump())


def collapse_repeated_closing(text: str, sentence: str) -> str:
    """Collapse repeated TRAILING occurrences of the mandatory closing line.

    The narrative directive asks the model to end a part with one exact
    closing sentence, but a narrating model sometimes appends it twice
    (playtest: the page-turning invitation echoed verbatim).  Only the
    trailing repeats (whitespace-separated) are merged into ONE occurrence:
    the EARLIEST one keeps its place, so the spacing before it is preserved
    and nothing that precedes it is touched.  An occurrence followed by more
    narration is the model's own structure and stays.  Trailing whitespace
    of the original text is preserved.
    """
    stripped = text.rstrip()
    pos = len(stripped)
    count = 0
    first_start = 0
    while pos > 0:
        start = stripped.rfind(sentence, 0, pos)
        if start < 0 or stripped[start + len(sentence):pos].strip():
            break
        first_start = start
        count += 1
        pos = start
        while pos > 0 and stripped[pos - 1].isspace():
            pos -= 1
    if count <= 1:
        return text
    return stripped[:first_start] + sentence + text[len(stripped):]


async def emit_stream(websocket: WebSocket, tokens: AsyncIterator[str],
                      story_more: bool = False) -> None:
    """Token-by-token emission; ``end`` carries the purged assembled text.

    ``story_more`` rides on the terminal frame: the client learns whether the
    subject's dossier still holds unseen fragments behind its cursor.  The
    final text is purged twice: the trailing formatting artifacts, then any
    repeated trailing occurrence of the mandatory closing line (one stay).
    """
    parts: list[str] = []
    async for token in tokens:
        parts.append(token)
        await websocket.send_json(TokenFrame(token=token).model_dump())
    text = strip_trailing_padding("".join(parts))
    for closing in (STORY_PAGINATION_SENTENCE, STORY_COMPLETE_SENTENCE):
        text = collapse_repeated_closing(text, closing)
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
