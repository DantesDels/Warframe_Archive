"""MediaWiki content queries: full fetch + delta metadata.

Mixin of ``MediaWikiSource``.  Fetches in batches of ``per_request_limit``
(50) with pagination via the ``continue`` token; does NOTHING but
communication (no cleaning).
"""

from __future__ import annotations

from .models import PageData, TouchedInfo


class MediaWikiQueryMixin:
    """Fetches pages (full content) and ``touched`` metadata."""

    def fetch_pages(self, titles: list[str]) -> dict[str, PageData]:
        """Fetches the full content of the requested pages (in batches of 50)."""
        result: dict[str, PageData] = {}
        for i in range(0, len(titles), self.http.per_request_limit):
            chunk = titles[i:i + self.http.per_request_limit]
            for data in self.http.paged({
                "action": "query", "format": "json", "formatversion": "2",
                "prop": "revisions|info",
                "rvprop": "content|timestamp", "rvslots": "main",
                "inprop": "touched|url",
                "titles": "|".join(chunk),
            }):
                for page in data.get("query", {}).get("pages", []):
                    if "pageid" not in page:
                        continue
                    revs = page.get("revisions") or []
                    content, ts = "", None
                    if revs:
                        slot = revs[0].get("slots", {}).get("main", {})
                        content = slot.get("content") or slot.get("*") or ""
                        ts = revs[0].get("timestamp")
                    pd = PageData(
                        pageid=page["pageid"],
                        title=page.get("title", ""),
                        namespace=page.get("ns", 0),
                        touched=page.get("touched"),
                        last_revision_timestamp=ts,
                        url=page.get("canonicalurl", ""),
                        content=content,
                    )
                    if pd.title:
                        result[pd.title] = pd
        return result

    def check_updates(self, titles: list[str]) -> dict[str, TouchedInfo]:
        """Light metadata (touched) used for delta computation."""
        result: dict[str, TouchedInfo] = {}
        for i in range(0, len(titles), self.http.per_request_limit):
            chunk = titles[i:i + self.http.per_request_limit]
            for data in self.http.paged({
                "action": "query", "format": "json", "formatversion": "2",
                "prop": "info", "inprop": "touched",
                "titles": "|".join(chunk),
            }):
                for page in data.get("query", {}).get("pages", []):
                    title = page.get("title", "")
                    if not title:
                        continue
                    result[title] = TouchedInfo(
                        pageid=page.get("pageid"),
                        title=title,
                        namespace=page.get("ns", 0),
                        touched=page.get("touched"),
                        missing=page.get("missing", False),
                    )
        return result