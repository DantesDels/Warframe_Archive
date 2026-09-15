"""Official French marketing site source (www.warframe.com/fr).

Implements :class:`BaseSource` for a plain HTML site: the catalogue is
discovered by crawling the internal links (see ``site_crawl``), freshness
comes from the ``ETag``/``Last-Modified`` headers, and content pages are
fetched as raw HTML (cleaned upstream by the ``HtmlCleaner``).
"""

from __future__ import annotations

import zlib
from urllib.parse import urlsplit

from .base import BaseSource
from .models import PageData, TouchedInfo
from .site_crawl import crawl_paths
from .site_http import SiteHttp


def site_page_id(path: str) -> int:
    """Deterministic per-route id (31-bit) for the SQL page identity.

    The site has no MediaWiki page ids; a stable integer keeps ``wiki_pages``
    and ``lore_chunks`` keyed per page instead of all collapsing on 0.
    """
    return zlib.crc32(("fr:" + path).encode("utf-8")) & 0x7FFFFFFF


class SiteHtmlSource(BaseSource):
    """Warframe marketing site, French routes (/fr)."""

    name = "warframe-com-fr"

    def __init__(self, config) -> None:
        self.config = config
        self.http = SiteHttp(
            site_url=config.site_url,
            user_agent=config.user_agent,
            timeout=config.request_timeout,
            max_retries=config.max_retries,
            retry_backoff=config.retry_backoff,
            min_sleep=config.min_sleep_between_requests,
        )

    def _host(self) -> str:
        return urlsplit(self.config.site_url).netloc.lower()

    def resolve_categories(self, category_names: list[str]) -> dict[str, set[str]]:
        """BFS-expands each seed path into the set of reachable page paths."""
        resolved = {}
        for seed in category_names:
            resolved[seed] = crawl_paths(
                self.http.get_text, seed,
                prefix=self.config.site_prefix,
                host=self._host(),
                exclude=self.config.site_exclude_segments,
                max_pages=self.config.site_max_pages,
            )
        return resolved

    def check_updates(self, titles: list[str]) -> dict[str, TouchedInfo]:
        """Lightweight HEAD: one ``ETag``/``Last-Modified`` signal per path."""
        touched = {}
        for title in titles:
            resp = self.http.head(title)
            if resp is None:
                touched[title] = TouchedInfo(pageid=None, title=title,
                                             missing=True)
                continue
            signal = resp.headers.get("ETag") or resp.headers.get(
                "Last-Modified")
            touched[title] = TouchedInfo(pageid=None, title=title,
                                         touched=signal)
        return touched

    def fetch_pages(self, titles: list[str]) -> dict[str, PageData]:
        """GETs each path and returns its raw HTML (also carrying ``touched``)."""
        pages = {}
        for title in titles:
            fetched = self.http.fetch(title)
            if fetched is None:
                continue
            html, touched = fetched
            pages[title] = PageData(
                pageid=site_page_id(title), title=title, namespace=0,
                touched=touched,
                url=self.config.site_url + title, content=html,
            )
        return pages


__all__ = ["SiteHtmlSource"]
