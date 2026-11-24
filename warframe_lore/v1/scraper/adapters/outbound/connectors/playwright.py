"""Optional Playwright connector for dynamic JS/SPA pages and catalogs."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from ....collect.crawl_filter import (
    infer_path_prefix,
    keep_crawl_url,
    matches_topic_tags,
)
from ....collect.dom_clean import dom_to_markdown, html_language
from ....collect.html_extract import extract_links, html_title
from ....collect.http import browser_headers
from ....collect.language import detect_language
from ....collect.spa import looks_like_spa, render_spa_page
from ....collect.wikitext import split_sections
from ....observability.progress import current_reporter, stop_requested
from ....ports.outbound.sources import CollectedPage, ConnectorContext


class PlaywrightConnector:
    """Render JS/SPA pages in headless Chromium with fast HTTP pre-check."""

    name = "playwright"
    kinds = ("website", "spa")

    def can_handle(self, source: dict[str, Any], ctx: ConnectorContext) -> bool:
        if not bool(ctx.limits.get("use_playwright", False)):
            return False
        return str(source.get("kind", "")).lower() in {"spa", "website"}

    def collect(
        self, source: dict[str, Any], ctx: ConnectorContext
    ) -> list[CollectedPage]:
        url = str(source.get("location", "")).strip()
        reporter = current_reporter(ctx.limits)
        force_spa = str(source.get("kind", "")).lower() == "spa"
        final_url, title, html, links, via = _load_root(url, ctx, force_spa)
        pages = [_build_page(final_url, title, html, via=via)]
        reporter.page(1, 1, final_url)

        same_host = bool(ctx.limits.get("same_host_only", True))
        tags = list(ctx.limits.get("topic_tags") or [])
        seed_host = (urlparse(final_url).hostname or "").lower()
        child_urls = _filter_links(links, final_url, seed_host, same_host, tags)
        max_pages = max(1, int(ctx.limits.get("max_pages_per_source", 25)))
        max_depth = max(0, int(ctx.limits.get("max_depth", 1)))
        if bool(ctx.limits.get("review_child_pages", False)):
            pending = ctx.limits.setdefault("pending_child_urls", [])
            cap = max(1, int(ctx.limits.get("max_manifest_urls", 250)))
            pending.extend({"url": c, "parent": final_url} for c in child_urls[:cap])
            return pages
        if max_depth <= 0 or max_pages <= 1:
            return pages
        for idx, child in enumerate(child_urls[: max_pages - 1], start=2):
            if stop_requested(ctx.limits):
                break
            page = _fetch_child(child, ctx)
            if page is not None:
                pages.append(page)
                reporter.page(idx, min(max_pages, len(child_urls) + 1), child)
        return pages


def _load_root(
    url: str, ctx: ConnectorContext, force_spa: bool
) -> tuple[str, str, str, list[str], str]:
    if not force_spa and ctx.client is not None:
        cached = bool(ctx.limits.get("use_cache", True))
        resp = ctx.client.get(url, headers=browser_headers(), use_cache=cached)
        body = bytes(getattr(resp, "content", b"") or b"")
        html = body.decode(getattr(resp, "encoding", None) or "utf-8", errors="replace")
        final_url = str(getattr(resp, "url", url) or url)
        sh = bool(ctx.limits.get("same_host_only", True))
        links = extract_links(html, final_url, same_host=sh)
        md = dom_to_markdown(html)
        max_pages = int(ctx.limits.get("max_pages_per_source", 1) or 1)
        need_js = looks_like_spa(html, len(links)) and (len(md) < 250 or max_pages > 1)
        if not need_js:
            return final_url, html_title(html) or final_url, html, links, "http"
    try:
        r = render_spa_page(url)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Playwright indisponible/échec : {exc}") from exc
    return r.final_url, r.title, r.html, r.links, "playwright"


def _build_page(
    url: str, title: str, html: str, *, via: str = "playwright"
) -> CollectedPage:
    md = dom_to_markdown(html)
    clean_title = title or html_title(html) or url
    sections = split_sections(clean_title, md) if md else []
    text = md or clean_title
    lang = detect_language(url, text, declared=html_language(html))
    return CollectedPage(
        title=clean_title, url=url, content=text,
        raw=html.encode("utf-8", errors="replace"), content_type="text/html",
        metadata={
            "content_markdown": text, "sections": sections, "language": lang,
            "page_title": clean_title, "page_url": url, "rendered_via": via,
        },
    )


def _filter_links(
    links: list[str], seed_url: str, seed_host: str, same_host: bool, tags: list[str],
) -> list[str]:
    seed_norm, prefix = seed_url.rstrip("/").lower(), infer_path_prefix(seed_url)
    out: list[str] = []
    for link in links:
        if link.rstrip("/").lower() == seed_norm:
            continue
        if same_host and (urlparse(link).hostname or "").lower() != seed_host:
            continue
        if keep_crawl_url(link, seed_url, prefix=prefix) and (
            not tags or matches_topic_tags(tags, link)
        ):
            out.append(link)
    return out


def _fetch_child(url: str, ctx: ConnectorContext) -> CollectedPage | None:
    try:
        cached = bool(ctx.limits.get("use_cache", True))
        resp = ctx.client.get(url, headers=browser_headers(), use_cache=cached)
        body = bytes(getattr(resp, "content", b"") or b"")
        html = body.decode(getattr(resp, "encoding", None) or "utf-8", errors="replace")
        final_url = str(getattr(resp, "url", url) or url)
        return _build_page(final_url, html_title(html), html, via="http")
    except Exception:  # noqa: BLE001
        return None
