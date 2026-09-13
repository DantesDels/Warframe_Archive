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

Usage (project root):
    python -m warframe_lore.engram.scripts.ingest [--glob out/Lore_*.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from sqlalchemy import select

from ...config import PROJECT_ROOT
from ...db import (
    LoreChunk,
    SQLDatabaseManager,
    sections_from_markdown,
)
from ..config import EngramConfig
from ..llm import LMStudioProvider

log = logging.getLogger("warframe_lore.engram.ingest")

BATCH = 64  # Taille de batch d'embedding (bge-m3 1024 dims; batch modéré).

_KIM_BUCKET_ID = "Lore_Dialogues_KIM"

# Clé de verrou advisory PostgreSQL (session-level) : un seul processus
# d'ingestion à la fois par base (anti-course double upsert / double
# embedding).
INGEST_LOCK_KEY = 0x4B494D5A  # "KIMZ"


def _is_kim_page(page: dict) -> bool:
    """The megafile entry belongs to the KIM dialogue bucket.

    Older megafiles only carry the bucket ``category`` (title): the KIM
    bucket title always contains "KIM".
    """
    return (page.get("bucket_id") == _KIM_BUCKET_ID
            or "KIM" in page.get("category", ""))


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


async def embed_pending(sessions, embeddings) -> int:
    """Computes embeddings for chunks without vectors (batches of ``BATCH``).

    The embedding dimension of the FIRST returned vector is validated against
    the ``lore_chunks.embedding`` column (vector(1024)): a model port change
    (wrong dimension) is detected before the first corrupted row is written.
    """
    embedding_dim = LoreChunk.__table__.c.embedding.type.dim
    embedded = 0
    while True:
        async with sessions() as session:
            missing = (await session.execute(
                select(LoreChunk.id, LoreChunk.content_markdown)
                .where(LoreChunk.embedding.is_(None))
                .limit(BATCH))).all()
        if not missing:
            break
        vectors = await embeddings.embed([content for _, content in missing])
        for vector in vectors:
            if len(vector) != embedding_dim:
                raise ValueError(
                    f"Embedding dimension mismatch: model returned "
                    f"{len(vector)}, column is vector({embedding_dim}). "
                    f"Align ENGRAM_EMBED_MODEL / ENGRAM_EMBED_DIM.")
        async with sessions() as session:
            for (chunk_id, _), vector in zip(missing, vectors, strict=True):
                chunk = await session.get(LoreChunk, chunk_id)
                chunk.embedding = vector
            await session.commit()
        embedded += len(missing)
        log.info("Embeddings computed: %d", embedded)
    return embedded


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
                page_id = int(page.get("_pageid") or 0)
                page_title = page["page_title"]
                is_kim = _is_kim_page(page)
                sections = None if is_kim else page.get("sections")
                if sections is None and not is_kim:
                    # Old megafiles with no "sections" yet: build the semantic
                    # sections on the fly (identical to the parser's output).
                    sections = sections_from_markdown(
                        page.get("content_markdown", ""), page_title)
                await manager.upsert_cleaned_page(
                    page_title=page_title,
                    category=page.get("category", ""),
                    page_id=page_id,
                    touched=page.get("touched"),
                    last_updated=page.get("last_updated"),
                    canon_status=page.get("canon_status", "canon"),
                    content_markdown=page.get("content_markdown", ""),
                    detect_kim_dialogues=is_kim,
                    sections=sections,
                )
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


if __name__ == "__main__":
    main()
