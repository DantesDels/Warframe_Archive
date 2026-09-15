"""Embedding ETL for the structured tables -> ``structured_chunks``.

Reads every row from the human-readable element tables (including both
dialogue tables), renders each to a searchable text (via
:mod:`warframe_lore.structured.rendering`), computes bge-m3 embeddings in
batches, and upserts into ``structured_chunks`` (idempotent: DELETE per kind
then INSERT).

Advisory-locked (``0x53545255`` = "STRU") — only one ETL run at a time.

Usage (project root):
    python -m warframe_lore.engram.scripts.embed_structured [--kinds ...]
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import select, text

from ...db import SQLDatabaseManager, StructuredChunk
from ...db.models import (
    GameAnnouncement,
    GameDialogue,
    GameQuest,
    GameUpdate,
    KimDialogue,
    LoreItem,
    Warframe,
)
from ...structured.rendering import render_row
from ..config import EngramConfig
from ..llm import LMStudioProvider

log = logging.getLogger("warframe_lore.engram.embed_structured")

BATCH = 64
LOCK_KEY = 0x53545255  # "STRU"

_TABLES: dict[str, type] = {
    "warframes": Warframe,
    "game_quests": GameQuest,
    "game_updates": GameUpdate,
    "game_announcements": GameAnnouncement,
    "lore_items": LoreItem,
    "game_dialogues": GameDialogue,
    "kim_dialogues": KimDialogue,
}


def _row_dict(row) -> dict:
    """Plain dict of the row columns, for the pure renderers."""
    return {column.key: getattr(row, column.key) for column in row.__table__.columns}


async def _embed_kind(session, provider, kind: str, model) -> int:
    """Replace one kind's chunks: DELETE then render+embed+INSERT."""
    await session.execute(
        text("DELETE FROM structured_chunks WHERE kind = :kind"), {"kind": kind}
    )
    rows = (await session.execute(select(model))).scalars().all()
    rendered = [_row_dict(row) for row in rows]
    total = 0
    for start in range(0, len(rendered), BATCH):
        batch = rendered[start : start + BATCH]
        pairs = [render_row(kind, row) for row in batch]
        vectors = await provider.embed([content for _, content in pairs])
        for (title, content), row, vector in zip(pairs, batch, vectors, strict=True):
            session.add(
                StructuredChunk(
                    kind=kind,
                    source_id=row["id"],
                    wiki_page_id=row["wiki_page_id"],
                    title=title,
                    content=content,
                    embedding=vector,
                )
            )
        await session.flush()  # bound memory: the rows leave the session
        total += len(batch)
    return total


async def run(cfg: EngramConfig, kinds: list[str] | None = None) -> int:
    """Full structured embedding (advisory-locked, idempotent)."""
    manager = SQLDatabaseManager(cfg.database_url)
    await manager.connect()
    provider = LMStudioProvider(
        base_url=cfg.lmstudio_base_url,
        chat_model=cfg.chat_model,
        embedding_model=cfg.embedding_model,
        api_key=cfg.lmstudio_api_key,
    )
    target_kinds = kinds or list(_TABLES)
    total = 0
    try:
        async with manager.advisory_lock(LOCK_KEY):
            sessions = manager._require_session_factory()
            for kind in target_kinds:
                async with sessions() as session:
                    count = await _embed_kind(session, provider, kind, _TABLES[kind])
                    await session.commit()
                total += count
                log.info("Inserted %s: %d chunks.", kind, count)
    finally:
        await provider.close()
        await manager.close()
    return total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Embed structured tables into structured_chunks."
    )
    parser.add_argument(
        "--kinds", nargs="*", default=None, help="Kinds to process (default: all)"
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    total = asyncio.run(run(EngramConfig.load(), args.kinds))
    log.info("Done: %d structured chunk(s) embedded.", total)


__all__ = ["BATCH", "LOCK_KEY", "main", "run"]

if __name__ == "__main__":
    main()
