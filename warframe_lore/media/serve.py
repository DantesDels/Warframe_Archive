"""Service d'images : téléchargement à la demande + charge utile /api/media."""

from __future__ import annotations

import logging
import urllib.error

from .const import CONTENT_IMAGE_BASE
from .network import download_to

log = logging.getLogger(__name__)

__all__ = ["MediaServeMixin"]


class MediaServeMixin:
    """Sert les PNG (cache local) et assemble la charge utile JSON pour l'UI."""

    def fetch_image(self, filename: str) -> bytes | None:
        """PNG mis en cache dans ``<output_dir>/media`` (téléchargement à la
        première demande). Retourne ``None`` si introuvable."""
        texture_location = self._by_file.get(filename)
        if not texture_location:
            return None
        local = self.media_dir / filename
        if local.is_file():
            return local.read_bytes()
        url = CONTENT_IMAGE_BASE + texture_location
        try:
            download_to(url, local, timeout=self.timeout)
        except (urllib.error.HTTPError, urllib.error.URLError) as error:
            log.warning("Image indisponible %s (%s) : %s",
                        filename, url, getattr(error, "code", error.reason))
            return None
        return local.read_bytes()

    def media_payload(
        self,
        page_titles_by_bucket: dict[str, list[str]],
        speakers: list[str],
    ) -> dict:
        """Charge utile JSON pour ``/api/media``.

        Ne contient que les images pertinentes pour l'archive (titres de
        pages + locuteurs KIM + représentants de bucket) — léger pour l'UI.
        """
        titles: dict[str, str] = {}
        buckets: dict[str, str] = {}
        for bucket_id, page_titles in page_titles_by_bucket.items():
            for title in page_titles:
                filename = self.lookup(title)
                if filename:
                    titles[title] = filename
                    if bucket_id not in buckets:
                        buckets[bucket_id] = filename
        speaker_images: dict[str, str] = {}
        for speaker in speakers:
            filename = self.lookup(speaker)
            if filename:
                speaker_images[speaker] = filename
        return {
            "available": self._ready,
            "count": len(self._texture),
            "titles": titles,
            "speakers": speaker_images,
            "buckets": buckets,
        }