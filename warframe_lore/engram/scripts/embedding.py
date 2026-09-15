"""Backfill of missing chunk embeddings (LM Studio ``bge-m3`` vectors).

Single responsibility: find the ``lore_chunks`` rows without a vector and
compute their embeddings in batches.  The dimension of the first returned
vector is validated against the ``embedding`` column type so a wrong model
port is detected before any corrupt row is written.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from ...db import LoreChunk

log = logging.getLogger("warframe_lore.engram.ingest")

# Taille de batch d'embedding (bge-m3 1024 dims; batch modéré).
BATCH = 64


async def embed_pending(sessions, embeddings) -> int:
    """Computes embeddings for all chunks without vectors (``BATCH`` at a time)."""
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


__all__ = ["BATCH", "embed_pending"]
