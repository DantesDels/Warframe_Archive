"""Nettoyage d'une page + écriture JSON/SQL en une passe."""

from __future__ import annotations

import logging

from ..output import build_output_entry

log = logging.getLogger("warframe_lore.scraper")


class ScraperIngestMixin:
    """Nettoie une page et la publie dans le megafile JSON et la base SQL."""

    async def _clean_and_store(self, *, bucket_spec, page_title: str,
                               page_obj, bucket_id: str):
        """Nettoie une page et l'écrit en JSON + SQL. Retourne l'entry JSON."""
        content_wikitext = getattr(page_obj, "content", "") or ""
        if not content_wikitext.strip():
            log.warning("Contenu vide pour '%s' — ignorée.", page_title)
            return None

        clean_output = self.cleaner.clean(content_wikitext)
        markdown_text = clean_output.markdown.strip()
        if len(markdown_text) < 20:
            log.warning("Page '%s' nettoyée en <20 caractères — ignorée.",
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

        # — Écriture JSON (megafile).
        output_entry = build_output_entry(
            page_title=page_title,
            category=bucket_spec.title,
            touched=touched,
            content_markdown=markdown_text,
            canon_status=canon_status,
            pageid=page_id,
            source_wiki_url=self.config.source_url_base,
        )

        # — Écriture SQL (upsert transactionnel) si la base est active.
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
                detect_kim_dialogues=(bucket_id == "Lore_Dialogues_KIM"),
            )

        log.debug("Page '%s' traitée (canon=%s).",
                  page_title, canon_status.value)
        return output_entry