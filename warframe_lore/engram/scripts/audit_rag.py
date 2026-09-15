"""RAG database audit: ``lore_chunks`` count + per-page preview.

Usage (project root):
    python -m warframe_lore.engram.scripts.audit_rag [--limit 3] [--name Leticia]
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ...db import LoreChunk, SQLDatabaseManager, WikiPage
from ..config import EngramConfig


async def run(cfg: EngramConfig, limit: int, name: str | None) -> None:
    manager = SQLDatabaseManager(cfg.database_url)
    await manager.connect()
    sessions = manager._require_session_factory()
    try:
        async with sessions() as session:
            filters = []
            if name:
                filters.append(WikiPage.page_title.ilike(f"%{name}%"))
                rows = (await session.execute(
                    select(WikiPage.page_title).where(*filters))).scalars().all()
                print(f"Pages matching '{name}': {len(rows)}")
                for title in rows[:20]:
                    print(f"  - {title}")
            total = (await session.execute(
                select(func.count()).select_from(LoreChunk))).scalar_one()
            print(f"LoreChunk (lore_chunks): {total} row(s)")
            if not total:
                print("Empty database: re-run ingestion (ingest.py).")
                return
            query = (select(LoreChunk)
                     .options(selectinload(LoreChunk.wiki_page))
                     .join(WikiPage)
                     .order_by(LoreChunk.wiki_page_id, LoreChunk.chunk_index)
                     .limit(limit))
            if name:
                query = query.where(*filters)
            rows = (await session.execute(query)).scalars()
            for i, chunk in enumerate(rows, 1):
                excerpt = " ".join((chunk.content_markdown or "").split())[:200]
                print(f"\n--- chunk {i} id={chunk.id} page_id={chunk.wiki_page_id} "
                      f"idx={chunk.chunk_index} page={chunk.wiki_page.page_title} ---")
                print(f"metadata: {chunk.chunk_metadata}")
                print(f"excerpt: {excerpt}...")
    finally:
        await manager.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG database audit (lore_chunks).")
    parser.add_argument("--limit", type=int, default=3,
                        help="Number of chunks to display (default: 3)")
    parser.add_argument("--name", type=str, default=None,
                        help="Filter by page title (e.g. Leticia)")
    args = parser.parse_args()
    asyncio.run(run(EngramConfig.load(), args.limit, args.name))


if __name__ == "__main__":
    main()
