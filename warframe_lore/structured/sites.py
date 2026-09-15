"""Row mapping for the official-site pages (warframes, updates, news)."""

from __future__ import annotations

import logging
import re
from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import GameAnnouncement, GameUpdate, Warframe
from .catalog import parse_warframe_page
from .news import parse_announcement, parse_update
from .store import store

log = logging.getLogger("warframe_lore.structured.sites")


async def ingest_site_page(
    session: AsyncSession,
    title: str,
    page_id: int,
    markdown: str,
    source_url: str | None,
    seen_frames: dict,
    seen_news: dict,
    counts: Counter,
) -> None:
    """Dispatches one official-site page to warframes/updates/announcements."""
    if title.startswith("/fr/game/warframes/"):
        rows = []
        for frame in parse_warframe_page(markdown, title, source_url):
            key = (frame.frame_name, frame.is_prime)
            if key in seen_frames and seen_frames[key] != page_id:
                continue  # base pages duplicate the Prime blurb
            seen_frames[key] = page_id
            rows.append(
                {
                    "frame_name": frame.frame_name,
                    "is_prime": frame.is_prime,
                    "description": frame.description,
                    "source_url": frame.source_url,
                }
            )
        await store(session, Warframe, page_id, rows, "warframes", counts)
    elif title.startswith("/fr/patch-notes/pc/"):
        update = parse_update(markdown, title, source_url)
        await store(
            session,
            GameUpdate,
            page_id,
            [
                {
                    "version": update.version,
                    "update_title": update.update_title,
                    "update_type": update.update_type,
                    "release_date": update.release_date,
                    "summary": update.summary,
                    "source_url": update.source_url,
                }
            ],
            "game_updates",
            counts,
        )
    elif title.startswith("/fr/news/"):
        announcement = parse_announcement(markdown, title, source_url)
        key = _norm_title(announcement.title)
        if key in seen_news and seen_news[key] != page_id:
            return  # duplicated article (alt slug / %20)
        seen_news[key] = page_id
        await store(
            session,
            GameAnnouncement,
            page_id,
            [
                {
                    "title": announcement.title,
                    "subtitle": announcement.subtitle,
                    "published_at": announcement.published_at,
                    "summary": announcement.summary,
                    "source_url": announcement.source_url,
                }
            ],
            "game_announcements",
            counts,
        )


def _norm_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().lower()
