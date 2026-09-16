"""Page cleaning + JSON/SQL writing in a single pass.

Each cleaned page is additionally decomposed into semantic sections
(``sections_from_markdown``), except for the KIM dialogue bucket which
keeps its dialogue mode (whole sessions + speakers).  The sections are both
persisted in the megafile entry (``"sections"``) and passed to the
structured ingestion of ``upsert_cleaned_page``.
"""

from __future__ import annotations

import logging

from ..db.chunks import (
    DEFAULT_CHUNK_MAX_CHARACTERS,
    DEFAULT_CHUNK_OVERLAP_CHARACTERS,
    sections_from_markdown,
)
from ..output import build_output_entry

log = logging.getLogger("warframe_lore.scraper")


class ScraperIngestMixin:
    """Cleans a page and publishes it to the JSON megafile and SQL database."""

    async def _clean_and_store(self, *, bucket_spec, page_title: str,
                               page_obj, bucket_id: str):
        """Cleans a page and writes it to JSON + SQL. Returns the JSON entry."""
        content_raw = getattr(page_obj, "content", "") or ""
        if not content_raw.strip():
            log.warning("Empty content for '%s' -- skipping.", page_title)
            return None

        cleaner = self._cleaner_for(bucket_spec)
        clean_output = cleaner.clean(content_raw)
        markdown_text = clean_output.markdown.strip()
        if len(markdown_text) < 20:
            log.warning("Page '%s' cleaned to <20 characters -- skipping.",
                        page_title)
            return None

        canon_status = self._page_canon_status(
            page_title=page_title,
            non_canon_detected_in_body=clean_output.non_canon_detected_in_body,
            canon_detected_in_body=clean_output.canon_detected_in_body,
        )

        page_id = getattr(page_obj, "pageid", 0)
        touched = getattr(page_obj, "touched", None)
        source_url = getattr(page_obj, "url", "") or (
            self.config.source_url_base + page_title.replace(" ", "_"))

        # -- Semantic sections (parser output): one section = N chunks
        # carrying "Page: X | Section: Y - " context.  KIM dialogues (and
        # only them) keep their dedicated dialogue mode.
        detect_kim_dialogues = (bucket_id == "Lore_Dialogues_KIM")
        sections = None
        if not detect_kim_dialogues:
            chunk_max = (self.db.chunk_max_characters if self.db is not None
                         else DEFAULT_CHUNK_MAX_CHARACTERS)
            chunk_overlap = (self.db.chunk_overlap_characters
                             if self.db is not None
                             else DEFAULT_CHUNK_OVERLAP_CHARACTERS)
            sections = sections_from_markdown(
                markdown_text, page_title,
                chunk_max_characters=chunk_max,
                chunk_overlap_characters=chunk_overlap,
            )

        # -- JSON writing (megafile).
        base_by_source = {
            "warframe-com-fr": self.config.site_url,
            "warframe-com-en": self.config.site_url,
            "mediawiki-warframe-fr": self.config.source_url_base_fr,
        }
        source_wiki_url = base_by_source.get(
            bucket_spec.source, self.config.source_url_base)
        is_fr_wiki = bucket_spec.source == "mediawiki-warframe-fr"
        output_entry = build_output_entry(
            page_title=page_title,
            category=bucket_spec.title,
            touched=touched,
            content_markdown=markdown_text,
            canon_status=canon_status,
            pageid=page_id,
            source_wiki_url=source_wiki_url,
            page_url=(source_url if is_fr_wiki else None),
        )
        output_entry.extra["bucket_id"] = bucket_id
        if is_fr_wiki and source_url:
            # Canonical page URL: engram re-upserts from the megafile and the
            # stored title ("Ballas (fr)") cannot rebuild it from a base.
            output_entry.extra["page_url"] = source_url
        if sections is not None:
            output_entry.extra["sections"] = sections

        # -- SQL writing (transactional upsert) if the database is active.
        if self.db is not None:
            await self.db.upsert_cleaned_page(
                page_title=page_title,
                category=bucket_id,
                page_id=page_id,
                touched=touched,
                last_updated=getattr(page_obj, "last_revision_timestamp", None),
                canon_status=canon_status,
                content_markdown=markdown_text,
                source_url=source_url,
                detect_kim_dialogues=detect_kim_dialogues,
                sections=sections,
            )

        log.debug("Page '%s' processed (canon=%s).",
                  page_title, canon_status.value)
        return output_entry
