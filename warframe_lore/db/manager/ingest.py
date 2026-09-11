"""Ingestion of a cleaned page: transactional upsert + chunks + dialogues.

Mixin of ``SQLDatabaseManager``.  The root page ``wiki_pages``, its chunks
``lore_chunks`` (preserving the embeddings) and the ``kim_dialogues`` rows
are persisted in a single transaction.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...output.models import CanonStatus
from ..kim_parser import extract_kim_messages
from ..models import KimDialogue, LoreChunk, WikiPage
from .sql_helpers import as_canon_status_string, parse_timestamp

log = logging.getLogger("warframe_lore.db")


class SQLIngestMixin:
    """Upsert of a wiki page + its chunks + its KIM dialogues."""

    async def upsert_cleaned_page(
        self,
        *,
        page_title: str,
        category: str,
        page_id: int,
        touched: str | None,
        last_updated: str | None,
        canon_status: CanonStatus | str,
        content_markdown: str,
        source_url: str = "",
        namespace: int = 0,
        detect_kim_dialogues: bool = True,
        sections: list[dict] | None = None,
    ) -> None:
        """Transactional upsert of a cleaned page + its chunks.

        A page in cleaned ``PageData`` state becomes:
          * 1 ``wiki_pages`` row (Insert or Update depending on existence);
          * N ``lore_chunks`` rows (atomically replaced);
          * M ``kim_dialogues`` rows if the page contains KIM dialogue.

        ``sections``: structured parser output
        (``[{"titre_page", "section", "contenu"}, ...]``).  When given, the
        chunks are built directly from these semantic sections (via
        ``ChunkManager.from_sections``) instead of re-splitting the whole
        page.  ``detect_kim_dialogues`` is then ignored (sections describe
        structured articles, not dialogues).

        All in a single transaction: on failure, nothing is partially
        persisted.
        """
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            async with session.begin():
                # --- 1. Upsert of the root page.
                # PostgreSQL: INSERT ... ON CONFLICT DO UPDATE (required by
                # the specification).  Other dialects (SQLite/tests): a
                # portable "read-then-write" fallback.
                await self._upsert_wiki_page(session, WikiPage(
                    page_id=page_id,
                    page_title=page_title,
                    category=category,
                    namespace=namespace,
                    touched=touched,
                    last_updated=parse_timestamp(last_updated),
                    canon_status=as_canon_status_string(canon_status),
                    source_url=source_url,
                    content_markdown=content_markdown,
                ))

                # --- 2. Chunks: update while PRESERVING the embeddings.
                # A DELETE+INSERT would destroy the already computed vectors
                # (RAG phase).  Unchanged chunks are kept (same content +
                # metadata), those whose text changed are updated (embedding
                # invalidated), and only the vanished indices are deleted.
                if sections:
                    rag_chunks = self.chunker.from_sections(sections)
                    kim_mode = False
                else:
                    rag_chunks = self.chunker.split(
                        content_markdown,
                        is_dialogue=detect_kim_dialogues,
                        page_title=page_title,
                    )
                    kim_mode = detect_kim_dialogues
                existing_chunks = (await session.execute(
                    select(LoreChunk).where(
                        LoreChunk.wiki_page_id == page_id))).scalars().all()
                existing_by_index = {chunk.chunk_index: chunk
                                     for chunk in existing_chunks}
                new_chunk_indices = {chunk.chunk_index for chunk in rag_chunks}
                for stale_index in set(existing_by_index) - new_chunk_indices:
                    await session.delete(existing_by_index[stale_index])
                for chunk in rag_chunks:
                    existing = existing_by_index.get(chunk.chunk_index)
                    if existing is None:
                        session.add(LoreChunk(
                            wiki_page_id=page_id,
                            chunk_index=chunk.chunk_index,
                            content_markdown=chunk.content_markdown,
                            chunk_metadata=chunk.metadata,
                        ))
                    elif (existing.content_markdown != chunk.content_markdown
                          or existing.chunk_metadata != chunk.metadata):
                        existing.content_markdown = chunk.content_markdown
                        existing.chunk_metadata = chunk.metadata
                        # The vector of the old text no longer matches the
                        # new content: better to invalidate it than to leave
                        # the embedding pointing at a shifted text.
                        existing.embedding = None

                # --- 3. KIM dialogues (if detected).
                kim_message_count = 0
                if kim_mode:
                    await session.execute(
                        delete(KimDialogue).where(
                            KimDialogue.wiki_page_id == page_id))
                    messages = extract_kim_messages(content_markdown)
                    kim_message_count = len(messages)
                    for message in messages:
                        session.add(KimDialogue(
                            wiki_page_id=page_id,
                            message_order=message.message_order,
                            speaker=message.speaker,
                            message_text=message.message_text,
                            player_choice=message.player_choice,
                            timestamp=message.timestamp,
                        ))

            log.debug("Upsert done for '%s' (page_id=%d, %d chunks, %d KIM)",
                      page_title, page_id, len(rag_chunks), kim_message_count)
        # NB: to keep the log readable when the page has no dialogue.
        if not content_markdown.strip():
            log.debug("Page '%s' with no cleaned content (ignored).", page_title)

    async def _upsert_wiki_page(self, session: AsyncSession,
                                page_record: WikiPage) -> None:
        """Upsert of a ``wiki_pages`` row adapted to the SQL dialect.

        PostgreSQL: ``INSERT ... ON CONFLICT (page_id) DO UPDATE``.
        Other dialects (SQLite for tests): read then insert/update.

        Robust to pages recreated on the wiki (same ``page_title`` but new
        ``page_id``): the former occurrence is first removed (cascade:
        chunks + dialogues) so the unique index ``idx_wiki_pages_title`` is
        not violated.
        """
        dialect_name = session.bind.dialect.name if session.bind else "sqlite"
        if dialect_name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            # --- 0. Safety reassignment (page recreated on the wiki).
            same_title_ids = (await session.execute(
                select(WikiPage.page_id).where(
                    WikiPage.page_title == page_record.page_title))).scalars().all()
            for stale_id in same_title_ids:
                if stale_id != page_record.page_id:
                    await session.execute(
                        delete(LoreChunk).where(LoreChunk.wiki_page_id == stale_id))
                    await session.execute(
                        delete(KimDialogue).where(KimDialogue.wiki_page_id == stale_id))
                    stale_page = await session.get(WikiPage, stale_id)
                    if stale_page is not None:
                        await session.delete(stale_page)

            statement = pg_insert(WikiPage).values(
                page_id=page_record.page_id,
                page_title=page_record.page_title,
                category=page_record.category,
                namespace=page_record.namespace,
                touched=page_record.touched,
                last_updated=page_record.last_updated,
                canon_status=page_record.canon_status,
                source_url=page_record.source_url,
                content_markdown=page_record.content_markdown,
            )
            statement = statement.on_conflict_do_update(
                index_elements=[WikiPage.page_id],
                set_={
                    "page_title": statement.excluded.page_title,
                    "category": statement.excluded.category,
                    "namespace": statement.excluded.namespace,
                    "touched": statement.excluded.touched,
                    "last_updated": statement.excluded.last_updated,
                    "canon_status": statement.excluded.canon_status,
                    "source_url": statement.excluded.source_url,
                    "content_markdown": statement.excluded.content_markdown,
                    "updated_at": func.now(),
                },
            )
            await session.execute(statement)
        else:
            existing_page = await session.get(WikiPage, page_record.page_id)
            if existing_page is None:
                session.add(page_record)
            else:
                existing_page.page_title = page_record.page_title
                existing_page.category = page_record.category
                existing_page.namespace = page_record.namespace
                existing_page.touched = page_record.touched
                existing_page.last_updated = page_record.last_updated
                existing_page.canon_status = page_record.canon_status
                existing_page.source_url = page_record.source_url
                existing_page.content_markdown = page_record.content_markdown
                existing_page.updated_at = datetime.now()