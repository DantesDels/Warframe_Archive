"""Per-bucket pipeline: resolution, delta, fetching, writing."""

from __future__ import annotations

import logging

log = logging.getLogger("warframe_lore.scraper")


class ScraperSyncMixin:
    """Coordinates buckets: from catalog to megafile publication."""

    async def _sync_buckets(self, force: bool) -> None:
        # 1. Resolution + delta (no writes) -- shared logic (DRY)
        #    with ``delta_plan`` used by ``cephalon diff``.
        log.info("Resolving %d bucket(s)...", len(self.buckets.specs))
        assigned_pages, pages_by_bucket = await self.resolve_buckets()

        # Purge pages that disappeared from all resolved categories.
        for spec in self.buckets.specs:
            live_titles = set(pages_by_bucket.get(spec.id, []))
            if self.db is not None:
                await self.db.purge_vanished_pages(spec.id, live_titles)

        unique_titles = list(assigned_pages.keys())
        log.info("Resolution complete: %d unique page(s) to consider.",
                 len(unique_titles))
        if not unique_titles:
            log.warning("No pages resolved -- nothing to do.")
            return

        # 2. Delta (pages that actually need fetching/updating).
        needs_fetch_per_bucket = await self.delta_plan(
            force=force, resolution=(assigned_pages, pages_by_bucket))
        total_todo = sum(len(titles) for titles in needs_fetch_per_bucket.values())
        log.info("Delta: %d page(s) to fetch/update (force=%s).",
                 total_todo, force)
        if total_todo == 0:
            log.info("Nothing changed -- megafiles and database up to date.")
            return

        # 4. Full content download for modified pages.
        fetched_by_title: dict[str, object] = {}
        for spec in self.buckets.specs:
            titles_to_fetch = needs_fetch_per_bucket.get(spec.id, [])
            if not titles_to_fetch:
                continue
            fetched_pages = self._source_for(spec).fetch_pages(titles_to_fetch)
            fetched_by_title.update(fetched_pages)
            log.info("Fetched %d page(s) for bucket '%s'.",
                     len(fetched_pages), spec.id)

        # 5. Cleaning + writing (JSON + SQL) per bucket.
        for spec in self.buckets.specs:
            titles_to_clean = needs_fetch_per_bucket.get(spec.id, [])
            if not titles_to_clean:
                continue
            new_entries = []
            for page_title in titles_to_clean:
                page = fetched_by_title.get(page_title)
                if page is None:
                    continue
                cleaned = await self._clean_and_store(bucket_spec=spec,
                                                      page_title=page_title,
                                                      page_obj=page,
                                                      bucket_id=spec.id)
                if cleaned is not None:
                    new_entries.append(cleaned)

            # JSON megafile for the bucket (incremental merge).
            if new_entries:
                live_titles = set(pages_by_bucket.get(spec.id, []))
                self.output.merge_and_write(
                    filename=spec.filename,
                    bucket_title=spec.title,
                    new_entries=new_entries,
                    metadata_note=self._source_note(spec.source),
                    live_titles=live_titles,
                )
                # Delta acknowledgment ONLY after successful JSON publication
                # (if the megafile failed, pages must not be marked as synced:
                # the database and JSON would diverge).
                if self.db is not None:
                    for entry in new_entries:
                        page = fetched_by_title.get(entry.page_title)
                        if page is None:
                            continue
                        await self.db.record_fetch(
                            bucket_id=spec.id,
                            page_title=entry.page_title,
                            page_id=getattr(page, "pageid", 0),
                            touched=getattr(page, "touched", None),
                        )
            else:
                log.warning("Bucket '%s': no cleaned pages to write.",
                            spec.id)

        log.info("Synchronization complete.")

    @staticmethod
    def _source_note(source_name: str) -> str:
        """Megafile provenance note describing the bucket's backend."""
        if source_name == "warframe-com-fr":
            return (
                "Content cleaned from www.warframe.com/fr (official site). "
                "French news, guides and narrative pages, canonical as published. "
                "Ready for LLM / NotebookLM ingestion."
            )
        if source_name == "warframe-com-en":
            return (
                "Content cleaned from www.warframe.com/en (official site). "
                "English news, guides and narrative pages, canonical as published. "
                "Ready for LLM / NotebookLM ingestion."
            )
        if source_name == "mediawiki-warframe-fr":
            return (
                "Content cleaned from the French WARFRAME wiki "
                "(fr.wiki.warframe.com, MediaWiki). Canon/non-canon status "
                "included. The English archives take precedence on conflicts. "
                "Ready for LLM / NotebookLM ingestion."
            )
        return (
            "Content cleaned from the WARFRAME wiki (MediaWiki). "
            "Canon/non-canon status included. "
            "Ready for LLM / NotebookLM ingestion."
        )
