"""Orchestrator for ``cephalon update``: the single-command chain.

Sequences the four phases of the update pipeline (scraper → structured
ETL → public export → static list regeneration) without human intervention.
kim-dm is intentionally excluded.

Each phase manages its own database connection except the last two
(export + lists), which share a single manager to avoid an extra round-trip.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("warframe_lore.update")


async def run_update(
    database_url: str,
    *,
    force: bool = False,
    glob_pattern: str = "out/Lore_*.json",
    langs: tuple[str, ...] = ("en", "fr"),
) -> dict[str, Any]:
    """Runs the full update chain and returns per-phase stats.

    The scraper and the structured ETL each manage their own database
    connection; the public export and the list regeneration share a
    single :class:`SQLDatabaseManager` opened for the duration of the
    last two phases.
    """
    results: dict[str, Any] = {}

    # ---- Phase 1: wiki sync → JSON (scraper manages its own DB conn).
    log.info("Phase 1/4 — scraper (wiki sync → JSON)")
    from ..scraper import Scraper

    scraper = Scraper(database_url=database_url)
    await scraper.arun(force=force)
    results["scraper"] = "ok"

    # ---- Phase 2: structured ETL (JSON → element tables) manages its own DB.
    log.info("Phase 2/4 — structured ETL")
    from ..engram.config import EngramConfig
    from ..structured.pipeline import run as structured_run

    counts = await structured_run(
        EngramConfig(database_url=database_url), glob_pattern)
    results["structured"] = dict(counts)

    # ---- Phases 3–4 share a single manager for the remaining work.
    from ..db.manager import SQLDatabaseManager

    manager = SQLDatabaseManager(database_url)
    await manager.connect()
    try:
        # Phase 3: public export (game entities → game_entities table).
        log.info("Phase 3/4 — public export")
        from ..export import PublicExportClient

        client = PublicExportClient(langs=langs)
        export_stats = await client.sync(manager, langs=langs, force=force)
        results["export"] = export_stats

        # Phase 4: regenerate static lists (story_eras.py).
        log.info("Phase 4/4 — static lists")
        from .lists import regenerate_story_eras

        lists_stats = await regenerate_story_eras(manager)
        results["lists"] = lists_stats
    finally:
        await manager.close()

    return results


__all__ = ["run_update"]
