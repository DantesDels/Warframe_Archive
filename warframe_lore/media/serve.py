"""Image service: on-demand download + /api/media payload."""

from __future__ import annotations

import logging
import urllib.error

from .const import CONTENT_IMAGE_BASE
from .network import download_to

log = logging.getLogger(__name__)

__all__ = ["MediaServeMixin"]


class MediaServeMixin:
    """Serve PNGs (local cache) and assemble the JSON payload for the UI."""

    def fetch_image(self, filename: str) -> bytes | None:
        """PNG cached in ``<output_dir>/media`` (downloaded on first request).
        Returns ``None`` if not found."""
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
            log.warning("Image unavailable %s (%s): %s",
                        filename, url, getattr(error, "code", error.reason))
            return None
        return local.read_bytes()

    def media_payload(
        self,
        page_titles_by_bucket: dict[str, list[str]],
        speakers: list[str],
    ) -> dict:
        """JSON payload for ``/api/media``.

        Only images relevant to the archive (page titles + KIM speakers +
        bucket representatives) — lightweight for the UI.
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
