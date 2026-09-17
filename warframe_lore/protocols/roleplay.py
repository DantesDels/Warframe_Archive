"""Shared wire protocol of the Cephalon roleplay channel (WebSocket).

Single source of truth for the frames exchanged between the Discord bot
(client) and the ENGRAM roleplay route (server).  Both sides import this
module: no frame type or field name is ever duplicated across the codebase.

Protocol: JSON lines over one WS connection.

    client -> server : message | persona | reset | comment
    server -> client : open | token | end | error | comment

A ``message`` turn ends with exactly one ``end`` (or ``error``) frame;
``token`` frames stream the reply in-between.  A ``comment`` request is
answered by exactly one ``comment`` frame (non-streamed).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

# Size of ONE narrative part: the number of dossier chunks a story turn reads
# and the step the client advances its cursor by.  Both sides read this single
# constant, so a part never re-narrates the passages of the previous one.
STORY_DOSSIER_PAGE = 12

# ----------------------------------------------------------------- frame types
FRAME_OPEN = "open"
FRAME_TOKEN = "token"
FRAME_END = "end"
FRAME_ERROR = "error"
FRAME_COMMENT = "comment"
FRAME_MESSAGE = "message"
FRAME_PERSONA = "persona"
FRAME_RESET = "reset"

# ------------------------------------------------------------------- personas
PERSONA_ORACLE = "oracle"
PERSONA_HOSTILE = "hostile"
PERSONA_MODES = frozenset({PERSONA_ORACLE, PERSONA_HOSTILE})

PersonaMode = Literal["oracle", "hostile"]


def _compact(data: dict[str, Any]) -> dict[str, Any]:
    """Drops the ``None`` fields for a smaller wire format."""
    return {k: v for k, v in data.items() if v is not None}


# ----------------------------------------------------------------- client -> server
class MessageFrame(BaseModel):
    """The main turn: user text, plus optional accredited context fields."""

    type: str = FRAME_MESSAGE
    text: str
    rag: bool = False
    # Storyteller turn: the request opens a narrative (not a document answer),
    # grounded on the archives from a chosen starting point (lens).
    story: bool = False
    story_lens: str | None = None
    # Targeted narrative subject: when the user names a specific entity, this
    # era overrides the lens menu and anchors the answer in that subject's era.
    targeted_era: str | None = None
    # Page-title anchor of that subject (the matched ``TARGETED_SUBJECT_ERAS``
    # key, e.g. ``"eleanor"``): the ENGRAM dossier retrieval walks the wiki
    # pages whose title contains this key, so the story corpus carries the
    # subject's own narrative page instead of only semantic neighbours.
    targeted_subject: str | None = None
    # Leverian Warframe: the canonical telling of this Warframe's story is in
    # Drusus' Leverian gallery; the model must ground its answer on that source.
    leverian_warframe: str | None = None
    # Search anchor of a CONTINUATION: an explicit follow-up ("continue") names
    # no subject of its own, so the bot replays the request that opened the
    # narrative and sends it here — retrieval then runs on the anchored subject
    # instead of on a subject-less message.  Only the SEARCH uses this field:
    # the model still receives ``text``.
    retrieval_text: str | None = None
    # Progress cursor of an open narrative: how many dossier chunks (in
    # ``STORY_DOSSIER_PAGE`` steps) have ALREADY been narrated.  Retrieval then
    # serves the NEXT page of the subject's dossier, so a continuation brings
    # new material instead of repeating the passages of the previous part.
    dossier_offset: int = 0
    user_id: str | int | None = None
    user_name: str | None = None
    user_role: str | None = None
    user_roles: list[str] | None = None
    role_status: str | None = None
    creator: bool | None = None
    creator_mention: str | None = None
    # Answer language requested for this channel ("fr" | "en"); ``None`` keeps
    # the persona default.  Both sides read the same field: no duplicated
    # literal, no silent drift.
    lang: str | None = None
    member_name: str | None = None
    member_roles: list[str] | None = None
    member_affiliated: bool | None = None
    reluctant: bool | None = None

    def payload(self) -> dict[str, Any]:
        return _compact(self.model_dump())


class PersonaFrame(BaseModel):
    """Persona switch (``oracle`` <-> ``hostile``), no reply emitted."""

    type: str = FRAME_PERSONA
    mode: PersonaMode

    def payload(self) -> dict[str, Any]:
        return _compact(self.model_dump())


class ResetFrame(BaseModel):
    """Wipes the user's short-term memory server-side (``!reset``)."""

    type: str = FRAME_RESET
    user_id: str | int

    def payload(self) -> dict[str, Any]:
        return _compact(self.model_dump())


class CommentRequestFrame(BaseModel):
    """One-shot member-card comment request (non-streamed)."""

    type: str = FRAME_COMMENT
    member_name: str
    member_roles: list[str] = []
    interactions: list[str] = []
    creator: bool = False
    reluctant: bool = False

    def payload(self) -> dict[str, Any]:
        return _compact(self.model_dump())


# ----------------------------------------------------------------- server -> client
class OpenFrame(BaseModel):
    """Sent on accept: announces the session id."""

    type: str = FRAME_OPEN
    session_id: str


class TokenFrame(BaseModel):
    """A token of the streaming reply."""

    type: str = FRAME_TOKEN
    token: str


class EndFrame(BaseModel):
    """Final frame of a turn, with the full accumulated text.

    ``story_more`` tells the client that MORE dossier material exists behind
    the cursor it sent: a narrative turn can then be continued (automatically
    or on order) and a client unaware of the field simply stops there.
    """

    type: str = FRAME_END
    text: str
    story_more: bool = False


@dataclass(frozen=True)
class TurnOutcome:
    """Terminal outcome of one streamed turn, as the CLIENT reads it."""

    story_more: bool = False

    @classmethod
    def from_end_frame(cls, payload: dict[str, Any] | None) -> TurnOutcome:
        """Read an ``end`` payload (``None`` or malformed: no continuation)."""
        if not payload:
            return cls()
        return cls(story_more=bool(payload.get("story_more")))


class ErrorFrame(BaseModel):
    """Terminal error: the turn is closed after this frame."""

    type: str = FRAME_ERROR
    message: str


class CommentFrame(BaseModel):
    """Reply to a ``comment`` request (non-streamed)."""

    type: str = FRAME_COMMENT
    text: str


__all__ = [
    "FRAME_OPEN", "FRAME_TOKEN", "FRAME_END", "FRAME_ERROR", "FRAME_COMMENT",
    "FRAME_MESSAGE", "FRAME_PERSONA", "FRAME_RESET",
    "PERSONA_ORACLE", "PERSONA_HOSTILE", "PERSONA_MODES", "PersonaMode",
    "STORY_DOSSIER_PAGE", "TurnOutcome",
    "MessageFrame", "PersonaFrame", "ResetFrame", "CommentRequestFrame",
    "OpenFrame", "TokenFrame", "EndFrame", "ErrorFrame", "CommentFrame",
]
