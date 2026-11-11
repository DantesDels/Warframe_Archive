"""French wiki source (fr.wiki.warframe.com) with a storage namespace.

The French wiki shares native MediaWiki page ids with the English wiki and
its titles collide on the unique ``page_title`` index, so every title
crossing this source's boundary is namespaced: ``"Ballas"`` is stored as
``"Ballas (fr)"`` with a dedicated high id range (``3*2^30 | crc32``).
English pages keep their native ids and titles — English remains the truth
authority and always sorts first in dossier ordering.
"""

from __future__ import annotations

import zlib

from .mediawiki import MediaWikiSource
from .models import PageData, TouchedInfo

FR_TITLE_SUFFIX = " (fr)"
FR_ID_PREFIX = "frwiki:"
FR_WIKI_ID_BASE = 3 << 30
FR_WIKI_ID_MASK = 0x3FFFFFFF


class FrenchMediaWikiSource(MediaWikiSource):
    """MediaWiki source of the French wiki (raw inside, stored outside).

    The API always receives the raw wiki titles (they do not exist with the
    ``(fr)`` suffix); every caller of this source sees the namespaced titles
    and page ids, keeping the pipeline, delta state and database consistent.
    """

    name = "mediawiki-warframe-fr"

    def __init__(self, config, *, api_url: str | None = None) -> None:
        super().__init__(config, api_url=api_url or config.api_url_fr,
                         category_label="Catégorie:", name=self.name)

    # ------------------------------------------------------ namespace
    def _to_stored(self, title: str) -> str:
        return title + FR_TITLE_SUFFIX

    def _to_raw(self, title: str) -> str:
        return title.removesuffix(FR_TITLE_SUFFIX)

    def _stored_page_id(self, raw_title: str) -> int:
        digest = zlib.crc32((FR_ID_PREFIX + raw_title).encode("utf-8"))
        return FR_WIKI_ID_BASE | (digest & FR_WIKI_ID_MASK)

    # --------------------------------------------- resolution / delta / fetch
    def resolve_categories(self, category_names: list[str]) -> dict[str, set[str]]:
        resolved = super().resolve_categories(category_names)
        return {name: {self._to_stored(title) for title in titles}
                for name, titles in resolved.items()}

    def resolve_prefix(self, prefix: str) -> set[str]:
        return {self._to_stored(title)
                for title in super().resolve_prefix(prefix)}

    def check_updates(self, titles: list[str]) -> dict[str, TouchedInfo]:
        raw_titles = sorted({self._to_raw(title) for title in titles})
        touched = super().check_updates(raw_titles)
        return {
            self._to_stored(raw): TouchedInfo(
                pageid=info.pageid,
                title=self._to_stored(info.title),
                namespace=info.namespace,
                touched=info.touched,
                missing=info.missing,
            )
            for raw, info in touched.items()
        }

    def fetch_pages(self, titles: list[str]) -> dict[str, PageData]:
        raw_titles = sorted({self._to_raw(title) for title in titles})
        out: dict[str, PageData] = {}
        for raw, page in super().fetch_pages(raw_titles).items():
            out[self._to_stored(raw)] = PageData(
                pageid=self._stored_page_id(raw),
                title=self._to_stored(raw),
                namespace=page.namespace,
                touched=page.touched,
                last_revision_timestamp=page.last_revision_timestamp,
                url=page.url,
                content=page.content,
            )
        return out


__all__ = ["FrenchMediaWikiSource"]
