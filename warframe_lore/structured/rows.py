"""Row mapping for fragment, quest and site megafile buckets.

Dialogue buckets (KIM, cinematics, quotes) live in ``dialogue_rows``.
This module owns ``ingest_bucket`` — the top-level dispatcher called by
``pipeline.run()``.
"""

from __future__ import annotations

import logging
from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import GameQuest, LoreItem
from .catalog import parse_quest
from .dialogue_rows import cinematic_page, kim_page, page_source_url, quotes_page
from .fragments import parse_fragments
from .sites import ingest_site_page
from .store import store

log = logging.getLogger("warframe_lore.structured.rows")


async def ingest_bucket(
    session: AsyncSession,
    known_ids: set[int],
    bucket: str,
    pages: list[dict],
    seen_frames: dict,
    seen_news: dict,
    counts: Counter,
) -> None:
    """Feeds one megafile bucket into the matching element tables."""
    for page in pages:
        title = page.get("page_title", "")
        page_id = int(page.get("_pageid") or 0)
        if page_id not in known_ids:
            log.info("Skip %r: page id %s absent from wiki_pages.", title, page_id)
            continue
        markdown = page.get("content_markdown", "")
        source_url = page_source_url(page)
        if bucket == "Lore_Dialogues_KIM":
            await kim_page(session, counts, page_id, title, markdown)
        elif bucket == "Lore_Dialogues_Quetes":
            await cinematic_page(session, counts, page_id, title, markdown)
        elif bucket == "Lore_Dialogues_Quotes":
            await quotes_page(session, counts, page_id, title, markdown)
        elif bucket == "Lore_Fragments":
            series, quest, rows = parse_fragments(markdown)
            await store(
                session,
                LoreItem,
                page_id,
                [
                    {
                        "series": series,
                        "item_name": row.item_name,
                        "context": quest,
                        "planet": row.planet,
                        "narrator": row.narrator,
                        "item_text": row.item_text,
                        "secret_text": row.secret_text,
                        "audio": row.audio,
                    }
                    for row in rows
                ],
                "lore_items",
                counts,
            )
        elif bucket == "Lore_Quetes":
            quest = parse_quest(markdown, title, source_url)
            if quest is None:
                continue
            await store(
                session,
                GameQuest,
                page_id,
                [
                    {
                        "quest_name": quest.quest_name,
                        "quest_type": quest.quest_type,
                        "release_note": quest.release_note,
                        "quest_context": quest.quest_context,
                        "source_url": quest.source_url,
                    }
                ],
                "game_quests",
                counts,
            )
        elif bucket == "Lore_Site_Officiel_FR":
            await ingest_site_page(
                session,
                title,
                page_id,
                markdown,
                source_url,
                seen_frames,
                seen_news,
                counts,
            )
