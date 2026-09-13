"""Wiki images attached to Oracle answers (Warframe Public Export cache).

Reuses the media index already built for the web UI — no second source of
truth, no new dependency: a lore answer naming a known entity gets its official
portrait attached.  Every network/disk access runs in a worker thread, so the
event loop is never blocked by a manifest load or a PNG download, and any
failure degrades to "no image" (best effort).
"""

from __future__ import annotations

import asyncio
import io
import logging
from pathlib import Path

import discord

from warframe_lore.media import MediaIndex

from ..text import content_words

log = logging.getLogger("warframe_lore.discord.media")

DEFAULT_CACHE_DIR = "cache/public_export/media"


class WikiImageService:
    """Lookup + attachment of cached Public Export PNGs."""

    def __init__(self, output_dir: Path | str,
                 cache_dir: str = DEFAULT_CACHE_DIR,
                 enabled: bool = True) -> None:
        self.enabled = enabled
        self._index = (MediaIndex(output_dir, cache_dir=cache_dir)
                       if enabled else None)

    async def ensure(self) -> bool:
        """Load the media index in a worker thread (idempotent, best effort)."""
        if self._index is None:
            return False
        return bool(await asyncio.to_thread(self._index.ensure))

    async def file_for(self, title: str) -> discord.File | None:
        """Attachment for one page title / speaker name, else ``None``."""
        return await self._attach([title] if title else [])

    async def file_for_text(self, text: str) -> discord.File | None:
        """Attachment for the first entity named in a free-form question."""
        return await self._attach(content_words(text))

    async def _attach(self, candidates: list[str]) -> discord.File | None:
        if self._index is None or not candidates:
            return None
        data, filename = await asyncio.to_thread(self._first_match, candidates)
        if data is None:
            return None
        return discord.File(io.BytesIO(data), filename=filename)

    def _first_match(self, candidates: list[str]) -> tuple[bytes | None, str]:
        """Blocking lookup: first candidate with a cached/downloadable PNG."""
        for candidate in candidates:
            filename = self._index.lookup(candidate)
            if not filename:
                continue
            data = self._index.fetch_image(filename)
            if data:
                return data, filename
        return None, ""


__all__ = ["DEFAULT_CACHE_DIR", "WikiImageService"]
