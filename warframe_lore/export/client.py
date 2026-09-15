"""Warframe Public Export client -- user-oriented facade.

Networking (index/assets) lives in ``fetch``, extraction in ``extract``,
database sync in ``sync``.  This class only holds state (configuration,
cache directory) and delegates.
"""

from __future__ import annotations

import logging
import urllib.request
from pathlib import Path

from .const import DEFAULT_LANGS, EXPORT_CATEGORIES

log = logging.getLogger(__name__)


class PublicExportClient:
    """Warframe Public Export client with incremental local cache."""

    def __init__(
        self,
        cache_dir="cache/public_export",
        langs: tuple[str, ...] = DEFAULT_LANGS,
        categories: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.langs = tuple(langs)
        self.categories = dict(categories or EXPORT_CATEGORIES)
        self.timeout = timeout

    # ------------------------------------------------------------- network
    def _http_get(self, url: str) -> bytes:
        """Binary GET with browser User-Agent + reasonable timeouts."""
        request = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.read()

    # ------------------------------------------------------------ delegation
    def fetch_index(self, lang: str) -> list[str]:
        from .fetch import fetch_index
        return fetch_index(self, lang)

    def asset_url(self, asset: str) -> str:
        from .fetch import asset_url
        return asset_url(self, asset)

    def fetch_asset(self, lang: str, asset: str, force: bool = False) -> bytes | None:
        from .fetch import fetch_asset
        return fetch_asset(self, lang, asset, force=force)

    def iter_entities_for(
        self,
        lang: str,
        category: str,
        payload: bytes,
    ) -> list:
        """Extracts :class:`GameEntity` instances from an asset (delegation)."""
        from .extract import extract_entities
        return extract_entities(self.categories, lang, category, payload)

    async def sync(
        self,
        manager,
        langs: tuple[str, ...] | None = None,
        force: bool = False,
    ) -> dict[str, int]:
        from .sync import sync_entities
        return await sync_entities(self, manager, langs=langs, force=force)
