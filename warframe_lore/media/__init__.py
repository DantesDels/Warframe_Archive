"""Warframe Public Export — media index + on-demand images.

Official pipeline (see https://wiki.warframe.com/w/Public_Export):
  * ``ExportManifest.json`` maps each ``uniqueName`` to a
    ``textureLocation`` (content-addressed URI);
  * Images are downloaded from ``https://content.warframe.com/PublicExport/``;
  * Since 2026 the manifest is fetched from the automatically maintained
    mirror (calamity-inc/warframe-public-export).

Public names: category manifests (``ExportWarframes_en.json``…) carry a
localised ``name`` + ``uniqueName``; they are used to map a wiki page title
/ KIM speaker to an image.

Caching: manifest + names stored in ``cache/public_export/media/``; PNGs
downloaded on demand into ``<output_dir>/media/`` (served offline afterwards).
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from .lookup import MediaLookupMixin
from .manifest import load_and_cache_manifest, load_and_cache_names
from .serve import MediaServeMixin

log = logging.getLogger(__name__)


class MediaIndex(MediaLookupMixin, MediaServeMixin):
    """Media index (uniqueName->texture, title->image) + local PNG cache.

    Lazy, thread-safe construction: the first network fetch (4.7 MB manifest
    + category manifests) is fault-tolerant — without a network the UI
    keeps working (just without images).
    """

    def __init__(self, output_dir, cache_dir="cache/public_export/media",
                 timeout: int = 60) -> None:
        self.output_dir = Path(output_dir)
        self.cache_dir = Path(cache_dir)
        self.timeout = timeout
        self.media_dir = self.output_dir / "media"
        self._lock = threading.RLock()
        self._ready = False
        self._attempted = False
        # uniqueName -> textureLocation; filename -> textureLocation
        self._texture: dict[str, str] = {}
        self._by_file: dict[str, str] = {}
        # normalised key (title / speaker) -> uniqueName
        self._names: dict[str, str] = {}

    def ensure(self, force: bool = False) -> bool:
        """Load (or download) the media index. Idempotent, thread-safe."""
        with self._lock:
            if self._ready and not force:
                return True
            if self._attempted and not force:
                return self._ready
            self._attempted = True
            try:
                self._texture, self._by_file = load_and_cache_manifest(
                    self.cache_dir, force, self.timeout)
                self._names = load_and_cache_names(
                    self.cache_dir, force, self.timeout)
                self._ready = True
                log.info("Media index ready: %d textures, %d names.",
                         len(self.texture_map()), len(self._names))
            except Exception as exc:  # noqa: BLE001 (mode best-effort)
                log.warning("Media index unavailable: %s", exc)
                self._ready = False
            return self._ready

    def available(self) -> bool:
        return self._ready


__all__ = ["MediaIndex"]