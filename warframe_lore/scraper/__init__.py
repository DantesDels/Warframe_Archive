"""Orchestrateur : résout les buckets, calcule le delta, récupère, nettoie,
écrit (JSON megafiles + base SQL).

Le paquet coordonne les couches :
    * ``canon``  -> signaux canon (Category:Speculation + signaux inline) ;
    * ``delta``  -> plan de delta / fraîcheur des pages ;
    * ``sync``   -> orchestration par bucket ;
    * ``ingest`` -> nettoyage + écriture d'une page.

Écriture **double**: chaque page nettoyée est à la fois inscrite dans son
megafile JSON (lecture humaine / NotebookLM) et dans la base relationnelle
(préparée pour le RAG vectoriel).  Le mode delta s'appuie sur la base SQL
(``sync_state`` en source de vérité).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from ..api import BucketConfig, CategoryCatalog, MediaWikiSource
from ..cleaner import CleanerConfig, WikitextCleaner
from ..config import Config, load_config
from ..db import SQLDatabaseManager
from ..output import MegafileManager
from .canon import CanonSignalsMixin
from .delta import ScraperDeltaMixin
from .ingest import ScraperIngestMixin
from .sync import ScraperSyncMixin

if TYPE_CHECKING:
    pass

log = logging.getLogger("warframe_lore.scraper")


class Scraper(CanonSignalsMixin, ScraperDeltaMixin,
              ScraperIngestMixin, ScraperSyncMixin):
    """Pipeline complet d'extraction/nettoyage/écriture.

    Mélange (mro) : doté des mixins ``canon``, ``delta``, ``ingest``,
    ``sync``.  La classe expose ``run``/``arun`` comme point d'entrée.

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


__all__ = ["Scraper"]