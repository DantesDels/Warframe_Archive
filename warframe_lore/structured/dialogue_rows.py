"""Row mapping for the dialogue megafile buckets (KIM, cinematics, quotes)."""

from __future__ import annotations

import logging
from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import GameDialogue
from .dialogues import parse_dialogues
from .store import store

log = logging.getLogger("warframe_lore.structured.dialogue_rows")

_KIM_PREFIX = "Kinemantik Instant Messenger/"


def kim_context(title: str) -> tuple[str, str]:
    """Derives ``(dialogue_kind, context_label)`` from a KIM page title."""
    if title.startswith(_KIM_PREFIX):
        return "kim", "KIM · " + title.rsplit("/", 1)[-1]
    return "quote", title.removesuffix("/Quotes")


def page_source_url(page: dict) -> str | None:
    """Builds the full source URL from the page dict's ``_source`` and title."""
    base = (page.get("_source") or "").rstrip("/")
    title = page.get("page_title") or ""
    if not base or not title:
        return None
    return base if base.endswith(title) else base + title


def dialogue_rows(kind: str, context: str, markdown: str) -> list[dict]:
    """Maps one dialogue page to ``game_dialogues`` row dicts."""
    return [
        {
            "dialogue_kind": kind,
            "context": context,
            "chapter": line.chapter,
            "speaker": line.speaker,
            "message_text": line.message_text,
            "player_choice": line.player_choice,
            "chemistry_gain": line.chemistry_gain,
            "message_order": line.message_order,
        }
        for line in parse_dialogues(kind, context, markdown)
    ]


async def kim_page(
    session: AsyncSession, counts: Counter, page_id: int, title: str, markdown: str
) -> None:
    kind, context = kim_context(title)
    rows = dialogue_rows(kind, context, markdown)
    await store(session, GameDialogue, page_id, rows, "game_dialogues", counts)


async def cinematic_page(
    session: AsyncSession, counts: Counter, page_id: int, title: str, markdown: str
) -> None:
    rows = dialogue_rows("cinematic", title.removesuffix("/Transcript"), markdown)
    await store(session, GameDialogue, page_id, rows, "game_dialogues", counts)


async def quotes_page(
    session: AsyncSession, counts: Counter, page_id: int, title: str, markdown: str
) -> None:
    rows = dialogue_rows("quote", title.removesuffix("/Quotes"), markdown)
    await store(session, GameDialogue, page_id, rows, "game_dialogues", counts)
