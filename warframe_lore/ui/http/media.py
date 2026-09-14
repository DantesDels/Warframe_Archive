"""Media routes of the local UI: index payload and cached image bytes.

Single responsibility: expose the Public Export media index to the frontend
(availability + counts) and fetch one cached image.  Best effort — without an
index the payload says ``available: false`` and a missing file yields the 404
body; the HTTP emission itself stays in the handler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...media import MediaIndex
    from ..data.store import LoreStore

UNAVAILABLE = {"available": False, "count": 0, "titles": {}, "speakers": {},
               "buckets": {}}
IMAGE_TYPES = ((".jpg", "image/jpeg"), (".jpeg", "image/jpeg"),
               (".gif", "image/gif"))
DEFAULT_IMAGE_TYPE = "image/png"
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
NOT_FOUND = {"error": "Not found"}
MISSING_IMAGE = {"error": "Image introuvable"}


def media_payload(store: LoreStore, media: MediaIndex | None) -> dict:
    """Media index summary for the frontend (never fails when unavailable)."""
    if media is None:
        return dict(UNAVAILABLE)
    media.ensure()
    if not media.available():
        return dict(UNAVAILABLE)
    return media.media_payload(
        page_titles_by_bucket=store.page_titles_by_bucket(),
        speakers=store.kim_speakers())


def media_image(media: MediaIndex | None,
                filename: str) -> tuple[bytes | None, str, dict]:
    """Cached image bytes, else ``(None, content type, 404 body)``."""
    if media is None or not filename:
        return None, DEFAULT_IMAGE_TYPE, NOT_FOUND
    media.ensure()
    if not media.available():
        return None, DEFAULT_IMAGE_TYPE, NOT_FOUND
    payload = media.fetch_image(filename)
    if payload is None:
        return None, DEFAULT_IMAGE_TYPE, MISSING_IMAGE
    return payload, image_type(filename), NOT_FOUND


def image_type(filename: str) -> str:
    """Content type of an image file name (PNG by default)."""
    lowered = filename.lower()
    for suffix, content_type in IMAGE_TYPES:
        if lowered.endswith(suffix):
            return content_type
    return DEFAULT_IMAGE_TYPE


__all__ = ["IMMUTABLE_CACHE", "image_type", "media_image", "media_payload"]
