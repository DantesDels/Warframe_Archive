"""Database orchestration that regenerates ``story_eras.py``.

Loads the curated mapping currently shipped in
:mod:`warframe_lore.discord.guild.story_eras` (every manual decision stays),
enriches it with the fresh archive tables (base Warframes, KIM contexts,
quest titles, Leverian page), and writes the file **only when the content
actually changes** so a no-op ``cephalon update`` produces no git noise.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from ..db.manager import SQLDatabaseManager
from .merge import (
    kim_subjects_from_contexts,
    leverian_frames_from_chunks,
    merge_sources,
    render_story_eras,
)

# Temporary marker while lists.py is split for reviewability.
STORY_ERAS_PATH = (
    Path(__file__).resolve().parents[1] / "discord" / "guild" / "story_eras.py")


async def regenerate_story_eras(
    manager: SQLDatabaseManager,
) -> dict[str, object]:
    """Regenerates ``story_eras.py`` from the archive database.

    Returns ``{"written": bool, "frames": int, "kim": int, "quests": int,
    "leverian": int}``.  ``written`` is ``True`` only when the rendered
    content differs from the current file (zero-diff on a no-op update).
    """
    from warframe_lore.discord.guild.story_eras import (  # curated base
        LEVERIAN_WARFRAMES,
        TARGETED_SUBJECT_ERAS,
    )

    async with manager._require_session_factory()() as session:
        frames = list((await session.execute(
            text("SELECT frame_name FROM warframes WHERE is_prime = false")
        )).scalars().all())
        kim_contexts = list((await session.execute(
            text("SELECT DISTINCT context FROM kim_dialogues "
                 "WHERE context IS NOT NULL AND context <> ''")
        )).scalars().all())
        quest_titles = list((await session.execute(
            text("SELECT quest_name FROM game_quests")
        )).scalars().all())
        leverian = await _leverian_chunks(session)

    mapping, leverian_frames = merge_sources(
        dict(TARGETED_SUBJECT_ERAS),
        LEVERIAN_WARFRAMES,
        frames=frames,
        kim_subjects=kim_subjects_from_contexts(kim_contexts),
        quest_titles=quest_titles,
        leverian_frames=leverian_frames_from_chunks(leverian, frames),
    )

    rendered = render_story_eras(mapping, leverian_frames)
    current = STORY_ERAS_PATH.read_text(encoding="utf-8")
    written = rendered != current
    if written:
        STORY_ERAS_PATH.write_text(rendered, encoding="utf-8")
    return {
        "written": written,
        "frames": len(frames),
        "kim": len(kim_contexts),
        "quests": len(quest_titles),
        "leverian": len(leverian_frames),
    }


async def _leverian_chunks(session) -> list[str]:
    """Markdown chunks of the ``Leverian`` gallery page (empty when absent)."""
    page_id = (await session.execute(
        text("SELECT page_id FROM wiki_pages WHERE page_title = 'Leverian'")
    )).scalar_one_or_none()
    if page_id is None:
        return []
    rows = await session.execute(
        text("SELECT content_markdown FROM lore_chunks "
             "WHERE wiki_page_id = :pid"),
        {"pid": page_id},
    )
    return list(rows.scalars().all())


__all__ = ["STORY_ERAS_PATH", "regenerate_story_eras"]
