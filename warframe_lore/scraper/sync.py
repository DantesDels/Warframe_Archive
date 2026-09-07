"""Pipeline par bucket : résolution, delta, récupération, écriture."""

from __future__ import annotations

import logging
from collections import defaultdict

from ..api import assign_pages

log = logging.getLogger("warframe_lore.scraper")


class ScraperSyncMixin:
    """Coordonne les buckets : du catalogue à la publication des megafiles."""

    async def _sync_buckets(self, force: bool) -> None:
        # 1. Résolution + delta (sans écriture) — logique partagée (DRY)
        #    avec ``delta_plan`` utilisé par ``cephalon diff``.
        log.info("Résolution de %d bucket(s)...", len(self.buckets.specs))
        resolved_buckets = [
            self.catalog.resolve(spec) for spec in self.buckets.specs
        ]
        assigned_pages = assign_pages(resolved_buckets)

        pages_by_bucket: dict[str, list[str]] = defaultdict(list)
        for page_title, bucket_spec in assigned_pages.items():
            pages_by_bucket[bucket_spec.id].append(page_title)

        # Purge des pages disparues de toutes les catégories résolues.
        for spec in self.buckets.specs:
            live_titles = set(pages_by_bucket.get(spec.id, []))
            if self.db is not None:
                await self.db.purge_vanished_pages(spec.id, live_titles)

        unique_titles = list(assigned_pages.keys())
        log.info("Résolution terminée : %d page(s) unique(s) à considérer.",
                 len(unique_titles))
        if not unique_titles:
            log.warning("Aucune page résolue — rien à faire.")
            return

        # 2. Delta (pages réellement à récupérer/mettre à jour).
        needs_fetch_per_bucket = await self.delta_plan(force=force)
        total_todo = sum(len(titles) for titles in needs_fetch_per_bucket.values())
        log.info("Delta : %d page(s) à récupérer/mettre à jour (force=%s).",
                 total_todo, force)
        if total_todo == 0:
            log.info("Rien n'a changé — megafiles et base à jour.")
            return

        # 4. Téléchargement du contenu complet pour les pages modifiées.
        fetched_by_title: dict[str, object] = {}
        for spec in self.buckets.specs:
            titles_to_fetch = needs_fetch_per_bucket.get(spec.id, [])
            if not titles_to_fetch:
                continue
            fetched_pages = self.source.fetch_pages(titles_to_fetch)
            fetched_by_title.update(fetched_pages)
            log.info("Récupéré %d page(s) pour le bucket '%s'.",
                     len(fetched_pages), spec.id)

        # 5. Nettoyage + écriture (JSON + SQL) par bucket.
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

            # Megafile JSON du bucket (fusion incrémentale).
            if new_entries:
                live_titles = set(pages_by_bucket.get(spec.id, []))
                self.output.merge_and_write(
                    filename=spec.filename,
                    bucket_title=spec.title,
                    new_entries=new_entries,
                    metadata_note=(
                        "Contenu nettoyé depuis le wiki WARFRAME (MediaWiki). "
                        "Statut canon/non-canon inclus. "
                        "Prêt pour ingestion LLM / NotebookLM."
                    ),
                    live_titles=live_titles,
                )
                # Acquittement delta SEULEMENT après publication JSON réussie
                # (si le megafile a échoué, il ne faut pas marquer la page
                # comme synchronisée : la base et le JSON divergeraient).
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
                log.warning("Bucket '%s' : aucune page nettoyée à écrire.",
                            spec.id)

        log.info("Synchronisation terminée.")