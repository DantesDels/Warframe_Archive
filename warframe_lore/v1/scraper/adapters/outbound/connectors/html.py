"""Generic HTML crawl connector."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ....collect.html_extract import extract_links, html_title, html_to_text
from ....collect.http import browser_headers
from ....ports.outbound.sources import CollectedPage, ConnectorContext


class HtmlConnector:
    name = "html"
    kinds = ("website", "api", "wiki")

    def can_handle(self, _source: dict[str, Any], _ctx: ConnectorContext) -> bool:
        return True

    def collect(
        self, source: dict[str, Any], ctx: ConnectorContext
    ) -> list[CollectedPage]:
        return collect_html(str(source.get("location", "")).strip(), ctx)


def collect_html(url: str, ctx: ConnectorContext) -> list[CollectedPage]:
    limits = ctx.limits
    max_pages = max(1, int(limits.get("max_pages_per_source", 1)))
    max_depth = max(0, int(limits.get("max_depth", 0)))
    same_host = bool(limits.get("same_host_only", True))
    use_cache = bool(limits.get("use_cache", True))
    queue: list[tuple[str, int]] = [(url, 0)]
    seen: set[str] = set()
    pages: list[CollectedPage] = []
    while queue and len(pages) < max_pages:
        current, depth = queue.pop(0)
        norm = current.rstrip("/")
        if norm in seen:
            continue
        seen.add(norm)
        resp = ctx.client.get(current, headers=browser_headers(), use_cache=use_cache)
        ctype = str(resp.content_type).lower()
        body = resp.content.decode(resp.encoding or "utf-8", errors="replace")
        if "html" not in ctype and "<html" not in body.lower():
            parsed_url = urlparse(str(resp.url))
            title = Path(parsed_url.path).name or parsed_url.netloc
            pages.append(CollectedPage(
                title=title, url=resp.url, content=body,
                from_cache=resp.from_cache, raw=resp.content, content_type=ctype))
            continue
        title = html_title(body) or urlparse(str(resp.url)).netloc
        pages.append(CollectedPage(
            title=title, url=resp.url, content=html_to_text(body),
            from_cache=resp.from_cache, raw=resp.content, content_type=ctype))
        if depth >= max_depth:
            continue
        for link in extract_links(body, resp.url, same_host=same_host):
            if link.rstrip("/") not in seen:
                queue.append((link, depth + 1))
    return pages
