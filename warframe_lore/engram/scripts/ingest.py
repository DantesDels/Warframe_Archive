"""ETL d'ingestion ENGRAM : megafiles JSON -> ``lore_chunks`` vectorisés.

Lit les megafiles ``out/Lore_*.json`` produits par la phase de nettoyage,
réutilise ``SQLDatabaseManager`` (``upsert_cleaned_page``) pour reconstituer
les pages + chunks, puis calcule les embeddings manquants via le fournisseur
LM Studio (``BAAI/bge-m3`` GGUF).

Utilisation (racine du projet) :
    python -m warframe_lore.engram.scripts.ingest [--glob out/Lore_*.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from sqlalchemy import select

from ...config import PROJECT_ROOT
from ...db import LoreChunk, SQLDatabaseManager, WikiPage
from ..config import EngramConfig
from ..llm import LMStudioProvider

log = logging.getLogger("warframe_lore.engram.ingest")

BATCH = 64  # Taille de lot d'embedding (bge-m3 ~576, on reste prudent).


def load_pages(glob_pattern: str) -> list[dict]:
    """Charge toutes les pages des megafiles JSON correspondant au motif."""
    pages: list[dict] = []
    for path in sorted(PROJECT_ROOT.glob(glob_pattern)):
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        bucket = data["pages"]
        if not isinstance(bucket, list):
            raise ValueError(f"{path}: 'pages' n'est pas une liste")
        pages.extend(bucket)
    return pages


async def embed_pending(sessions, embeddings) -> int:
    """Calcule les embeddings des chunks sans vecteur (lots de ``BATCH``)."""
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
        async with sessions() as session:
            for (chunk_id, _), vector in zip(missing, vectors):
                chunk = await session.get(LoreChunk, chunk_id)
                chunk.embedding = vector
            await session.commit()
        embedded += len(missing)
        log.info("Embeddings calculés : %d", embedded)
    return embedded


async def run(cfg: EngramConfig, glob_pattern: str) -> int:
    pages = load_pages(glob_pattern)
    log.info("Pages chargées : %d", len(pages))

    manager = SQLDatabaseManager(cfg.database_url)
    await manager.connect()
    provider = LMStudioProvider(
        base_url=cfg.lmstudio_base_url,
        chat_model=cfg.chat_model,
        embedding_model=cfg.embedding_model,
        api_key=cfg.lmstudio_api_key,
    )
    try:
        processed = 0
        for page in pages:
            page_id = int(page.get("_pageid") or 0)
            await manager.upsert_cleaned_page(
                page_title=page["page_title"],
                category=page.get("category", ""),
                page_id=page_id,
                touched=page.get("touched"),
                last_updated=page.get("last_updated"),
                canon_status=page.get("canon_status", "canon"),
                content_markdown=page.get("content_markdown", ""),
            )
            processed += 1
        log.info("Pages upsertées : %d", processed)
        embedded = await embed_pending(manager._require_session_factory(), provider)
        return embedded
    finally:
        await provider.close()
        await manager.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestion ENGRAM (embeddings).")
    parser.add_argument("--glob", default="out/Lore_*.json",
                        help="Motif glob des megafiles (défaut: out/Lore_*.json)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO)
    embedded = asyncio.run(run(EngramConfig.load(), args.glob))
    log.info("Terminé : %d embedding(s) calculé(s).", embedded)


if __name__ == "__main__":
    main()