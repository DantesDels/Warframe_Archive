"""Orchestrator: resolves buckets, computes the delta, fetches, cleans,
writes (JSON megafiles + SQL database).

The package coordinates the layers:
    * ``canon``  -> canon signals (Category:Speculation + inline signals);
    * ``delta``  -> delta plan / page freshness;
    * ``sync``   -> per-bucket orchestration;
    * ``ingest`` -> cleaning + writing of a page.

**Dual** write: each cleaned page is both written to its JSON megafile
(human reading / NotebookLM) and to the relational database (prepared
for vector RAG).  Delta mode relies on the SQL database
(``sync_state`` as source of truth).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from ..api import BucketConfig, CategoryCatalog, MediaWikiSource, SiteHtmlSource
from ..cleaner import CleanerConfig, HtmlCleaner, WikitextCleaner
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
    """Full extraction/cleaning/writing pipeline.

    MRO (mro): equipped with ``canon``, ``delta``, ``ingest``,
    ``sync`` mixins.  The class exposes ``run``/``arun`` as entry points.

    Args:
        config: runtime configuration (API, directories, database).
        bucket_config: logical bucket definitions.
        database_url: async PostgreSQL connection URL.
    """

    def __init__(self, config: Config | None = None,
                 bucket_config: BucketConfig | None = None,
                 database_url: str | None = None) -> None:
        self.config = config or load_config()
        self.buckets = bucket_config or BucketConfig()
        self.sources = {
            "mediawiki-warframe": MediaWikiSource(self.config),
            "warframe-com-fr": SiteHtmlSource(self.config),
        }
        # Backward-compatible default alias (the wiki remains the main source).
        self.source = self.sources.get("mediawiki-warframe")
        self.catalog = CategoryCatalog(self.sources)
        self.cleaners = {
            "mediawiki-warframe": WikitextCleaner(
                cleaner_config=CleanerConfig.load()),
            "warframe-com-fr": HtmlCleaner(),
        }
        self.cleaner = self.cleaners.get("mediawiki-warframe")
        self.output = MegafileManager(self.config.output_dir)
        # ``database_url=None`` -> JSON-only mode (--skip-sql).
        self.database_url = database_url or (
            self.config.database_url if database_url is not None else None)
        self.db: SQLDatabaseManager | None = None
        if self.database_url:
            self.db = SQLDatabaseManager(self.database_url)
        # Speculation category resolution (for page-level canon_status):
        # set of speculative page titles.
        self._speculation_titles: set[str] = set()

    def _source_for(self, spec):
        """Backend implementation owning ``spec`` (falls back to the wiki)."""
        return self.sources.get(spec.source, self.source)

    def _cleaner_for(self, spec):
        """Cleaner matching the bucket's source format (wiki vs site HTML)."""
        return self.cleaners.get(spec.source, self.cleaner)

    # ------------------------------------------------------------------ runs
    def run(self, force: bool = False) -> None:
        """Runs a full sync cycle (synchronous entry point)."""
        asyncio.run(self.arun(force=force))

    async def arun(self, force: bool = False) -> None:
        """Async version of the main pipeline."""
        if self.db is not None:
            await self.db.connect()
        try:
            await self._resolve_speculation_titles()
            await self._sync_buckets(force=force)
        finally:
            if self.db is not None:
                await self.db.close()


__all__ = ["Scraper"]
