"""Look-up queries mapping title/uniquename -> image filename."""

from __future__ import annotations

from .names import normalize_key, sanitize_filename

__all__ = ["MediaLookupMixin"]


class MediaLookupMixin:
    """Map page title / speaker / uniqueName to a PNG filename."""

    def texture_map(self) -> dict[str, str]:
        return dict(self._texture)

    def filename_for_unique(self, unique_name: str) -> str | None:
        location = self._texture.get(unique_name)
        if not location:
            return None
        return sanitize_filename(location)

    def filename_for_title(self, title: str) -> str | None:
        uid = self._names.get(normalize_key(title))
        return self.filename_for_unique(uid) if uid else None

    def lookup(self, key: str) -> str | None:
        """Page title or speaker name -> image filename."""
        return self.filename_for_title(key)