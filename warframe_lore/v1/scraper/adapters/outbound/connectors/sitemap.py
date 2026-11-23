"""Sitemap connector with sitemapindex recursion, lastmod delta and page fetch."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from ....collect.dom_clean import html_language
from ....collect.html_extract import html_title, markdown_to_text
from ....collect.http import browser_headers
from ....collect.language import detect_language
from ....collect.sitemap_xml import parse_sitemap_xml
from ....collect.wikitext import split_sections
from ....observability.progress import current_reporter, stop_requested
from ....ports.outbound.sources import CollectedPage, ConnectorContext

MAX_CHILD_SITEMAPS = 10


class SitemapConnector:
    name = "sitemap"
    kinds = ("sitemap", "website")

    def can_handle(self, source: dict[str, Any], _ctx: ConnectorContext) -> bool:
        loc = str(source.get("location", "")).lower()
        kind = str(source.get("kind", "")).lower()
        return kind == "sitemap" or loc.endswith("sitemap.xml") or "sitemap" in loc

    def collect(
        self, source: dict[str, Any], ctx: ConnectorContext
    ) -> list[CollectedPage]:
        url = str(source.get("location", "")).strip()
        use_cache = bool(ctx.limits.get("use_cache", True))
        max_pages = max(1, int(ctx.limits.get("max_pages_per_source", 25)))
        entries = _collect_entries(ctx, url, max_pages, use_cache)
        state = cast_state(ctx, url)
        incremental = bool(ctx.limits.get("incremental", True))
        reporter = current_reporter(ctx.limits)
        pages: list[CollectedPage] = []
        for idx, (loc, lastmod) in enumerate(entries[:max_pages], start=1):
            if stop_requested(ctx.limits):
                break
            if lastmod and state.get(loc, "") == lastmod and incremental:
                continue
            pages.append(_fetch_entry(ctx, url, loc, lastmod, use_cache))
            if lastmod:
                state[loc] = lastmod
            reporter.page(idx, min(len(entries), max_pages), loc)
        return pages


def _collect_entries(
    ctx: ConnectorContext, url: str, max_pages: int, use_cache: bool
) -> list[tuple[str, str]]:
    resp = ctx.client.get(url, use_cache=use_cache)
    child_sitemaps, urls = parse_sitemap_xml(bytes(getattr(resp, "content", b"")))
    if urls:
        return urls[:max_pages]
    out: list[tuple[str, str]] = []
    for child_url in child_sitemaps[:MAX_CHILD_SITEMAPS]:
        if len(out) >= max_pages or stop_requested(ctx.limits):
            break
        try:
            c_resp = ctx.client.get(child_url, use_cache=use_cache)
        except Exception:
            continue
        _, child_urls = parse_sitemap_xml(bytes(getattr(c_resp, "content", b"")))
        out.extend(child_urls)
    return out[:max_pages]


def _fetch_entry(
    ctx: ConnectorContext, sitemap_url: str, loc: str, lastmod: str, use_cache: bool
) -> CollectedPage:
    fallback = CollectedPage(
        title=loc.rsplit("/", 1)[-1] or loc,
        url=loc,
        content=f"Source sitemap: {sitemap_url}\nlastmod: {lastmod}",
        metadata={"lastmod": lastmod, "sitemap": sitemap_url},
    )
    try:
        resp = ctx.client.get(loc, headers=browser_headers(), use_cache=use_cache)
    except Exception:
        return fallback
    ctype = str(getattr(resp, "content_type", "") or "").lower()
    raw = bytes(getattr(resp, "content", b""))
    text = raw.decode(getattr(resp, "encoding", None) or "utf-8", errors="replace")
    if "html" not in ctype and "<html" not in text.lower():
        return fallback
    title = html_title(text) or urlparse(loc).path.rsplit("/", 1)[-1] or loc
    markdown = markdown_to_text(text)
    if not markdown.strip():
        return fallback
    lang = detect_language(loc, markdown, html_language(text))
    return CollectedPage(
        title=title,
        url=loc,
        content=markdown,
        from_cache=bool(getattr(resp, "from_cache", False)),
        raw=raw,
        content_type=ctype or "text/html",
        metadata={
            "lastmod": lastmod, "sitemap": sitemap_url, "language": lang,
            "content_markdown": markdown, "sections": split_sections(title, markdown),
            "page_title": title, "page_url": loc,
        },
    )


def cast_state(ctx: ConnectorContext, url: str) -> dict[str, str]:
    root = ctx.limits.setdefault("connector_state", {})
    sm = root.setdefault("sitemaps", {})
    bucket = sm.setdefault(url, {})
    return bucket  # type: ignore[return-value]
