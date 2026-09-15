"""ETL: JSON megafiles -> the six human-readable element tables.

Reads the cleaned megafiles again (the same sources as the ENGRAM ingest)
and derives, page by page, the structured rows of ``game_dialogues``,
``lore_items``, ``warframes``, ``game_quests``, ``game_updates`` and
``game_announcements``.

Each page is refreshed in its own transaction (DELETE + INSERT), so re-runs
are idempotent and replace the previous derivation, exactly like the
``replace_dialogues`` KIM API does.  Pages whose id is not in
``wiki_pages`` are skipped (foreign-key safety).  The ``rows``/``sites``
modules map each megafile bucket to row dicts; ``store`` persists them.

Usage (project root):
    python -m warframe_lore.structured.pipeline [--glob out/Lore_*.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections import Counter

from sqlalchemy import select

from ..config import PROJECT_ROOT
from ..db import SQLDatabaseManager
from ..db.models import WikiPage
from ..engram.config import EngramConfig
from .rows import ingest_bucket

log = logging.getLogger("warframe_lore.structured.pipeline")

# Independent from the ENGRAM ingest lock: the element tables never
# contend with the page/chunk/embedding pipeline.
PIPELINE_LOCK_KEY = 0x4550524D  # "EPRM"


def load_buckets(glob_pattern: str) -> list[tuple[str, list[dict]]]:
    """Loads ``(bucket_stem, pages)`` from the megafiles."""
    buckets: list[tuple[str, list[dict]]] = []
    for path in sorted(PROJECT_ROOT.glob(glob_pattern)):
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        buckets.append((path.stem, data["pages"]))
    return buckets


async def run(cfg: EngramConfig, glob_pattern: str) -> Counter:
    """Ingests every megafile; returns the inserted row count per table."""
    buckets = load_buckets(glob_pattern)
    log.info("Buckets loaded: %d", len(buckets))
    manager = SQLDatabaseManager(cfg.database_url)
    await manager.connect()
    counts = Counter()
    try:
        async with manager.advisory_lock(PIPELINE_LOCK_KEY):
            async with manager._require_session_factory()() as session:
                known_ids = set(
                    (await session.execute(select(WikiPage.page_id))).scalars().all()
                )
                log.info("wiki_pages known: %d", len(known_ids))
                seen_frames: dict[tuple[str, bool], int] = {}
                seen_news: dict[str, int] = {}
                for bucket, pages in buckets:
                    await ingest_bucket(
                        session,
                        known_ids,
                        bucket,
                        pages,
                        seen_frames,
                        seen_news,
                        counts,
                    )
    finally:
        await manager.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Structured element tables ETL (dialogues, lore, quests)."
    )
    parser.add_argument(
        "--glob",
        default="out/Lore_*.json",
        help="Megafile glob pattern (default: out/Lore_*.json)",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    counts = asyncio.run(run(EngramConfig.load(), args.glob))
    for table, total in sorted(counts.items()):
        log.info("Inserted %s: %d row(s).", table, total)


__all__ = ["main", "run"]

if __name__ == "__main__":
    main()
