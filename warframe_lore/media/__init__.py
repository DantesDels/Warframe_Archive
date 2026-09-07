"""Warframe Public Export — index média + images à la demande.

Pipeline officiel (cf. https://wiki.warframe.com/w/Public_Export) :
  * ``ExportManifest.json`` associe chaque ``uniqueName`` à une
    ``textureLocation`` (URI content-addressed) ;
  * L'image se télécharge à ``https://content.warframe.com/PublicExport/`` ;
  * Depuis 2026 le manifest se récupère depuis le miroir maintenu
    automatiquement (calamity-inc/warframe-public-export).

Noms publics : les manifests de catégories (``ExportWarframes_en.json``…)
portent ``name`` (localisé) + ``uniqueName`` ; on les utilise pour mapper un
titre de page wiki / un locuteur KIM vers une image.

Mise en cache : manifest + noms dans ``cache/public_export/media/`` ; les PNG
téléchargés à la demande dans ``<output_dir>/media/`` (hors-ligne ensuite).
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
    """Index média (uniqueName->texture, titre->image) + cache PNG local.

    Construction paresseuse et thread-safe : le premier accès réseau
    (manifest 4,7 Mo + manifests de catégories) est tolérant à l'échec —
    sans réseau l'interface continue (simplement sans images).
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
        # uniqueName -> textureLocation ; filename -> textureLocation
        self._texture: dict[str, str] = {}
        self._by_file: dict[str, str] = {}
        # clé normalisée (titre / locuteur) -> uniqueName
        self._names: dict[str, str] = {}

    def ensure(self, force: bool = False) -> bool:
        """Charge (ou télécharge) l'index média. Idempotent, thread-safe."""
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
                log.info("Index média prêt : %d textures, %d noms.",
                         len(self.texture_map()), len(self._names))
            except Exception as exc:  # noqa: BLE001 (mode best-effort)
                log.warning("Index média indisponible : %s", exc)
                self._ready = False
            return self._ready

    def available(self) -> bool:
        return self._ready


__all__ = ["MediaIndex"]