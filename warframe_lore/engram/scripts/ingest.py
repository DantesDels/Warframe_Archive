"""ENGRAM ingestion ETL: JSON megafiles -> vectorized ``lore_chunks``.

Reads the ``out/Lore_*.json`` megafiles produced by the cleaning phase,
reuses ``SQLDatabaseManager`` (``upsert_cleaned_page``) to reconstruct
pages + chunks, then computes missing embeddings via the LM Studio
provider (``BAAI/bge-m3`` GGUF).

Chunking mode per page:
  * structured articles use the semantic sections already stored by the
    scraper (``page["sections"]``, re-split on the fly if absent) -- each
    chunk vectorized WITH its ``"Page: X | Section: Y - "`` context;
  * KIM dialogue pages (bucket ``Lore_Dialogues_KIM``) keep the dialogue
    mode (whole sessions, ``speakers`` metadata).

Provenance is preserved on (re)upsert: ``category`` prefers the bucket id
(``page["bucket_id"]``) written by the scraper, and ``source_url`` is
rebuilt from the ``_source`` base + the page title.

Usage (project root):
    python -m warframe_lore.engram.scripts.ingest [--glob out/Lore_*.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from ...config import PROJECT_ROOT
from ...db import (
    SQLDatabaseManager,
    sections_from_markdown,
)
from ..config import EngramConfig
from ..llm import LMStudioProvider
from .embedding import embed_pending

log = logging.getLogger("warframe_lore.engram.ingest")

_KIM_BUCKET_ID = "Lore_Dialogues_KIM"

# Clé de verrou advisory PostgreSQL (session-level) : un seul processus
# d'ingestion à la fois par base (anti-course double upsert / double
# embedding).
INGEST_LOCK_KEY = 0x4B494D5A  # "KIMZ"


def _is_kim_page(page: dict) -> bool:
    """The megafile entry belongs to the KIM dialogue bucket.

    ``bucket_id`` (written by the scraper) always wins; the category-title
    heuristic only covers older megafiles without a ``bucket_id``.
    """
    bucket_id = page.get("bucket_id")
    if bucket_id:
        return bucket_id == _KIM_BUCKET_ID
    return "KIM" in page.get("category", "")


def _page_source_url(page: dict) -> str:
    """Reconstructs the full page URL from the megafile provenance fields.

    ``page_url`` carries the canonical page URL when the stored title was
    suffixed (e.g. French wiki ``"Ballas (fr)"``): return it as-is.  ``_source``
    already holds the canonical page URL (site routes and wiki titles alike)
    for the other pages: return it when it ends with the title, otherwise
    build it from the base + title (legacy base-form megafiles).
    """
    canonical = page.get("page_url")
    if canonical:
        return canonical
    base = (page.get("_source") or "").rstrip("/")
    title = page.get("page_title") or ""
    if not base or not title:
        return ""
    title_key = title.rstrip("/") if title.startswith("/") \
        else title.replace(" ", "_")
    if base.endswith(title_key):
        return base
    if title.startswith("/"):
        return base + title
    return base + "/" + title_key


def load_pages(glob_pattern: str) -> list[dict]:
    """Loads all pages from JSON megafiles matching the pattern."""
    pages: list[dict] = []
    for path in sorted(PROJECT_ROOT.glob(glob_pattern)):
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        bucket = data["pages"]
        if not isinstance(bucket, list):
            raise ValueError(f"{path}: 'pages' is not a list")
        pages.extend(bucket)
    return pages


def _upsert_kwargs(page: dict, is_kim: bool) -> dict:
    """Maps a megafile entry to the ``upsert_cleaned_page`` arguments."""
    sections = None if is_kim else page.get("sections")
    if sections is None and not is_kim:
        # Old megafiles with no "sections" yet: build the semantic
        # sections on the fly (identical to the parser's output).
        sections = sections_from_markdown(
            page.get("content_markdown", ""), page.get("page_title", ""))
    return {
        "page_title": page["page_title"],
        "category": page.get("bucket_id") or page.get("category", ""),
        "page_id": int(page.get("_pageid") or 0),
        "touched": page.get("touched"),
        "last_updated": page.get("last_updated"),
        "canon_status": page.get("canon_status", "canon"),
        "content_markdown": page.get("content_markdown", ""),
        "source_url": _page_source_url(page),
        "detect_kim_dialogues": is_kim,
        "sections": sections,
    }


async def run(cfg: EngramConfig, glob_pattern: str) -> int:
    pages = load_pages(glob_pattern)
    log.info("Pages loaded: %d", len(pages))

    manager = SQLDatabaseManager(cfg.database_url)
    await manager.connect()
    provider = LMStudioProvider(
        base_url=cfg.lmstudio_base_url,
        chat_model=cfg.chat_model,
        embedding_model=cfg.embedding_model,
        api_key=cfg.lmstudio_api_key,
    )
    try:
        # Verrou advisory : deux ingestions concurrentes attendent au lieu de
        # courir (upsert + embeddings seraient dupliqués / interrompus).
        async with manager.advisory_lock(INGEST_LOCK_KEY):
            processed = 0
            for page in pages:
                await manager.upsert_cleaned_page(
                    **_upsert_kwargs(page, _is_kim_page(page)))
                processed += 1
            log.info("Pages upserted: %d", processed)
            embedded = await embed_pending(
                manager._require_session_factory(), provider)
            return embedded
    finally:
        await provider.close()
        await manager.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="ENGRAM ingestion (embeddings).")
    parser.add_argument("--glob", default="out/Lore_*.json",
                        help="Megafile glob pattern (default: out/Lore_*.json)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO)
    embedded = asyncio.run(run(EngramConfig.load(), args.glob))
    log.info("Done: %d embedding(s) computed.", embedded)


__all__ = ["main", "run"]

if __name__ == "__main__":
    main()
