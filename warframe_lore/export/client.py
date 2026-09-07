"""Client du Warframe Public Export — façade orientée utilisateur.

Le réseau (index/actifs) vit dans ``fetch``, l'extraction dans ``extract``,
la synchronisation en base dans ``sync``.  Cette classe ne garde que l'état
(configuration, répertoire de cache) et délègue.
"""

from __future__ import annotations

import logging
import urllib.request
from pathlib import Path

from .const import DEFAULT_LANGS, EXPORT_CATEGORIES

log = logging.getLogger(__name__)


class PublicExportClient:
    """Client du Warframe Public Export avec cache local incrémental."""

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

    # ------------------------------------------------------------- réseau
    def _http_get(self, url: str) -> bytes:
        """GET binaire avec User-Agent navigateur + timeouts raisonnables."""
        request = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.read()

    # ------------------------------------------------------------ délégation
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
        """Extrait les :class:`GameEntity` d'un actif (délégation)."""
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