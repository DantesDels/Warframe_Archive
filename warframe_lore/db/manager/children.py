"""Synchronisation of a page's child rows: chunks and KIM dialogues.

Single responsibility: replace the children of ONE ``wiki_pages`` row, inside the
caller's transaction.

Chunks are reconciled by index so the already computed embeddings SURVIVE — a
DELETE+INSERT would destroy the RAG vectors: unchanged chunks are kept, changed
ones are updated with their embedding invalidated, and only the vanished indices
are deleted.  KIM dialogues carry no derived data: they are replaced wholesale.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..kim_parser import extract_kim_messages
from ..models import KimDialogue, LoreChunk

if TYPE_CHECKING:
    from ..chunks import RAGChunk


async def sync_chunks(session: AsyncSession, page_id: int,
                      chunks: Sequence[RAGChunk]) -> None:
    """Reconcile ``lore_chunks`` with ``chunks``, preserving embeddings."""
    existing = (await session.execute(
        select(LoreChunk).where(
            LoreChunk.wiki_page_id == page_id))).scalars().all()
    by_index = {row.chunk_index: row for row in existing}
    for stale_index in set(by_index) - {c.chunk_index for c in chunks}:
        await session.delete(by_index[stale_index])
    for chunk in chunks:
        row = by_index.get(chunk.chunk_index)
        if row is None:
            session.add(LoreChunk(
                wiki_page_id=page_id,
                chunk_index=chunk.chunk_index,
                content_markdown=chunk.content_markdown,
                chunk_metadata=chunk.metadata))
        elif (row.content_markdown != chunk.content_markdown
                or row.chunk_metadata != chunk.metadata):
            row.content_markdown = chunk.content_markdown
            row.chunk_metadata = chunk.metadata
            # The vector of the old text no longer matches the new content:
            # invalidate it rather than leave an embedding on a shifted text.
            row.embedding = None


async def replace_dialogues(session: AsyncSession, page_id: int,
                            content_markdown: str) -> int:
    """Replace the ``kim_dialogues`` of a page; return the message count."""
    await session.execute(
        delete(KimDialogue).where(KimDialogue.wiki_page_id == page_id))
    messages = extract_kim_messages(content_markdown)
    for message in messages:
        session.add(KimDialogue(
            wiki_page_id=page_id,
            message_order=message.message_order,
            speaker=message.speaker,
            message_text=message.message_text,
            player_choice=message.player_choice))
    return len(messages)


__all__ = ["replace_dialogues", "sync_chunks"]
