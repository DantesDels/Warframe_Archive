"""Orchestrateur : résout les buckets, calcule le delta, récupère, nettoie,
écrit (JSON megafiles + base SQL PostgreSQL).

Ce module coordonne les couches :
    api      -> MediaWikiSource (extraction) + CategoryCatalog (buckets)
    cleaner  -> WikitextCleaner (nettoyage + signaux canon)
    output   -> MegafileManager (megafiles JSON)
    db       -> SQLDatabaseManager (table wiki_pages/lore_chunks/kim_dialogues)

Écriture **double**: chaque page nettoyée est à la fois inscrite dans son
megafile JSON (lecture humaine / NotebookLM) et dans la base relationnelle
(préparée pour le RAG vectoriel).  Le mode delta s'appuie sur la base SQL
(``sync_state`` en source de vérité).
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from pathlib import Path
from typing import Callable

from .api import BucketConfig, CategoryCatalog, MediaWikiSource, assign_pages
from .cleaner import CleanerConfig, WikitextCleaner
from .config import Config, load_config
from .db import SQLDatabaseManager
from .output import (
    CanonStatus,
    MegafileManager,
    build_output_entry,
    merge_canon_status,
)

log = logging.getLogger("warframe_lore.scraper")


class Scraper:
    """Pipeline complet d'extraction/nettoyage/écriture.

    Args:
        config: configuration runtime (API, répertoires, base de données).
        bucket_config: définition des buckets logiques.
        database_url: URL de connexion PostgreSQL (async).
    """

    def __init__(self, config: Config | None = None,
                 bucket_config: BucketConfig | None = None,
                 database_url: str | None = None) -> None:
        self.config = config or load_config()
        self.buckets = bucket_config or BucketConfig()
        self.source = MediaWikiSource(self.config)
        self.catalog = CategoryCatalog(self.source)
        self.cleaner = WikitextCleaner(cleaner_config=CleanerConfig.load())
        self.output = MegafileManager(self.config.output_dir)
        # ``database_url=None`` -> mode JSON only (--skip-sql).
        self.database_url = database_url or (
            self.config.database_url if database_url is not None else None)
        self.db: SQLDatabaseManager | None = None
        if self.database_url:
            self.db = SQLDatabaseManager(self.database_url)
        # Résolution de la catégorie Speculation (pour le canon_status au
        # niveau page) : ensemble des titres de pages spéculatifs.
        self._speculation_titles: set[str] = set()

    # ------------------------------------------------------------------ runs
    def run(self, force: bool = False) -> None:
        """Exécute un cycle complet de synchro (point d'entrée synchrone)."""
        asyncio.run(self.arun(force=force))

    async def arun(self, force: bool = False) -> None:
        """Version asynchrone du pipeline principal."""
        if self.db is not None:
            await self.db.connect()
        try:
            await self._resolve_speculation_titles()
            await self._sync_buckets(force=force)
        finally:
            if self.db is not None:
                await self.db.close()

    # -------------------------------------------------------- canon statut
    async def _resolve_speculation_titles(self) -> None:
        """Développe la ``Category:Speculation`` pour connaître les pages
        considérées comme conjecturales par le wiki."""
        resolve_members: Callable[..., dict[str, set[str]]] = \
            self.source.resolve_categories
        mapping = resolve_members(["Speculation"])
        self._speculation_titles = mapping.get("Speculation", set())
        if self._speculation_titles:
            log.info("Category:Speculation résolue : %d page(s) conjecturales",
                     len(self._speculation_titles))

    def _page_canon_status(
        self,
        page_title: str,
        non_canon_detected_in_body: bool,
        canon_detected_in_body: bool,
    ) -> CanonStatus:
        """Calcule le statut canon d'une page (niveau page + signaux inline).

        Priorités : une page listée dans ``Category:Speculation`` OU qui
        contient un template ``{{Speculation}}`` en ligne -> speculation ;
        sinon canon.
        """
        page_level_speculative = page_title in self._speculation_titles
        inline_non_canon = non_canon_detected_in_body

        page_status = (
            CanonStatus.SPECULATION if page_level_speculative
            else CanonStatus.CANON
        )
        body_status = (
            CanonStatus.SPECULATION if inline_non_canon
            else CanonStatus.CANON
        )
        # merge_canon_status retient le statut le plus faible (priorité la
        # plus haute) : un seul signal spéculatif suffit à classer en spec.
        return merge_canon_status(page_status, body_status)

    # ------------------------------------------------------------ pipeline
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
            log.info("Rien n'a changé — megafiles et base à jour." )
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

    async def delta_plan(self, force: bool = False,
                         bucket_config: BucketConfig | None = None
                         ) -> dict[str, list[str]]:
        """Calcule le delta sans rien écrire (mode prévisualisation ``diff``).

        Reproduit la résolution des buckets + la comparaison des ``touched``
        sans télécharger les contenus ni écrire en base.  Retourne un mapping
        ``bucket_id -> [titres à mettre à jour]``.
        """
        buckets = bucket_config or self.buckets
        resolved_buckets = [
            self.catalog.resolve(spec) for spec in buckets.specs
        ]
        assigned_pages = assign_pages(resolved_buckets)

        pages_by_bucket: dict[str, list[str]] = defaultdict(list)
        for page_title, bucket_spec in assigned_pages.items():
            pages_by_bucket[bucket_spec.id].append(page_title)
        if not assigned_pages:
            return {}

        touched_info = self.source.check_updates(list(assigned_pages.keys()))
        plan: dict[str, list[str]] = defaultdict(list)
        for page_title, bucket_spec in assigned_pages.items():
            bucket_id = bucket_spec.id
            info = touched_info.get(page_title)
            if info is None or info.missing:
                continue
            modified_timestamp = info.touched
            needs_fetch = True
            if not force and self.db is not None:
                needs_fetch = not await self._page_is_fresh(
                    bucket_id, page_title, modified_timestamp)
            if needs_fetch:
                plan[bucket_id].append(page_title)
        return dict(plan)

    async def _page_is_fresh(self, bucket_id: str, page_title: str,
                             touched: str | None) -> bool:
        """Vrai si la page en base est déjà à jour (même ``touched``)."""
        if touched is None:
            return False  # pas de référence : on (re)télécharge
        state = await self.db.fetch_sync_state(bucket_id)
        stored = state.get(page_title)
        return stored is not None and stored.get("touched") == touched

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