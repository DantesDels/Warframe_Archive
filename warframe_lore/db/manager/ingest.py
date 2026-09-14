"""Ingestion of a cleaned page: transactional upsert + chunks + dialogues.

Mixin of ``SQLDatabaseManager``: ONE transaction persists the root page
``wiki_pages``, its chunks ``lore_chunks`` (embeddings preserved) and its
``kim_dialogues`` rows — on failure nothing is partially written.  The mechanics
live in :mod:`page_upsert` (dialect-aware upsert) and :mod:`children` (chunk and
dialogue synchronisation); this module only orchestrates and decides where the
chunks come from.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ...output.models import CanonStatus
from ..models import WikiPage
from .children import replace_dialogues, sync_chunks
from .page_upsert import upsert_wiki_page
from .sql_helpers import as_canon_status_string, parse_timestamp

if TYPE_CHECKING:
    from ..chunks import RAGChunk

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
          * N ``lore_chunks`` rows (atomically reconciled, embeddings kept);
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
                await upsert_wiki_page(session, WikiPage(
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
                chunks, kim_mode = self._rag_chunks(
                    content_markdown, page_title, detect_kim_dialogues, sections)
                await sync_chunks(session, page_id, chunks)
                dialogues = (await replace_dialogues(session, page_id,
                                                     content_markdown)
                             if kim_mode else 0)
            log.debug("Upsert done for '%s' (page_id=%d, %d chunks, %d KIM)",
                      page_title, page_id, len(chunks), dialogues)
        # NB: to keep the log readable when the page has no dialogue.
        if not content_markdown.strip():
            log.debug("Page '%s' with no cleaned content (ignored).", page_title)

    def _rag_chunks(self, content_markdown: str, page_title: str,
                    detect_kim_dialogues: bool,
                    sections: list[dict] | None) -> tuple[list[RAGChunk], bool]:
        """Chunks of the page, plus whether KIM dialogues must be (re)detected.

        With structured ``sections`` the chunks come from the semantic sections;
        otherwise the whole markdown is split (dialogue mode included).
        """
        if sections:
            return self.chunker.from_sections(sections), False
        return (self.chunker.split(content_markdown,
                                   is_dialogue=detect_kim_dialogues,
                                   page_title=page_title),
                bool(detect_kim_dialogues))


__all__ = ["SQLIngestMixin"]
