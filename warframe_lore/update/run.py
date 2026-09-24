"""Orchestrator for ``cephalon update``: the single-command chain.

Sequences the five phases of the update pipeline (scraper → structured
ETL → public export → static list regeneration → RAG embeddings) without
human intervention.  kim-dm is intentionally excluded.

Each phase manages its own database connection except the export and
static-list phases, which share a single manager to avoid an extra
round-trip.  The RAG-embedding phase reuses the canonical ENGRAM ETLs
(``ingest`` + ``embed_structured``), each advisory-locked and idempotent.
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
    two middle phases.  The final phase reuses the ENGRAM ingestion and
    structured-embedding ETLs so the RAG corpora (``lore_chunks`` +
    ``structured_chunks``) all carry the fresh vectors.
    """
    results: dict[str, Any] = {}

    # ---- Phase 1: wiki sync → JSON (scraper manages its own DB conn).
    log.info("Phase 1/5 — scraper (wiki sync → JSON)")
    from ..scraper import Scraper

    scraper = Scraper(database_url=database_url)
    await scraper.arun(force=force)
    results["scraper"] = "ok"

    # ---- Phase 2: structured ETL (JSON → element tables) manages its own DB.
    log.info("Phase 2/5 — structured ETL")
    from ..engram.config import EngramConfig
    from ..structured.pipeline import run as structured_run

    config = EngramConfig(database_url=database_url)
    counts = await structured_run(config, glob_pattern)
    results["structured"] = dict(counts)

    # ---- Phases 3–4 share a single manager for the remaining work.
    from ..db.manager import SQLDatabaseManager

    manager = SQLDatabaseManager(database_url)
    await manager.connect()
    try:
        # Phase 3: public export (game entities → game_entities table).
        log.info("Phase 3/5 — public export")
        from ..export import PublicExportClient

        client = PublicExportClient(langs=langs)
        export_stats = await client.sync(manager, langs=langs, force=force)
        results["export"] = export_stats

        # Phase 4: regenerate static lists (story_eras.py).
        log.info("Phase 4/5 — static lists")
        from .lists import regenerate_story_eras

        lists_stats = await regenerate_story_eras(manager)
        results["lists"] = lists_stats
    finally:
        await manager.close()

    # ---- Phase 5: RAG embeddings.  Backfill the pending lore_chunks
    # vectors (new/changed chunk text) and re-embed the element tables
    # into structured_chunks.  Both canonical ETLs are idempotent and
    # advisory-locked; they need the LM Studio endpoint (EngramConfig).
    log.info("Phase 5/5 — RAG embeddings")
    from ..engram.scripts.embed_structured import run as embed_structured_run
    from ..engram.scripts.ingest import run as ingest_run

    results["lore_chunks"] = await ingest_run(config, glob_pattern)
    results["structured_chunks"] = await embed_structured_run(config)

    return results


__all__ = ["run_update"]
