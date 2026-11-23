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
from ....collect.language import detect_language
from ....collect.spa import render_spa_page
from ....collect.wikitext import split_sections
from ....observability.progress import current_reporter, stop_requested
from ....ports.outbound.sources import CollectedPage, ConnectorContext


class PlaywrightConnector:
    """Render JS/SPA pages in headless Chromium with clean Markdown + link crawl."""

    name = "playwright"
    kinds = ("website", "spa")

    def can_handle(self, source: dict[str, Any], ctx: ConnectorContext) -> bool:
        if not bool(ctx.limits.get("use_playwright", False)):
            return False
        kind = str(source.get("kind", "")).lower()
        return kind in {"spa", "website"}

    def collect(
        self, source: dict[str, Any], ctx: ConnectorContext
    ) -> list[CollectedPage]:
        url = str(source.get("location", "")).strip()
        reporter = current_reporter(ctx.limits)
        try:
            rendered = render_spa_page(url)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Playwright indisponible/échec : {exc}") from exc
        pages = [_build_page(rendered.final_url, rendered.title, rendered.html)]
        reporter.page(1, 1, rendered.final_url)

        same_host = bool(ctx.limits.get("same_host_only", True))
        tags = list(ctx.limits.get("topic_tags") or [])
        seed_host = (urlparse(rendered.final_url).hostname or "").lower()
        child_urls = _filter_links(
            rendered.links, rendered.final_url, seed_host, same_host, tags
        )
        max_pages = max(1, int(ctx.limits.get("max_pages_per_source", 25)))
        max_depth = max(0, int(ctx.limits.get("max_depth", 1)))
        review = bool(ctx.limits.get("review_child_pages", False))
        if review:
            pending = ctx.limits.setdefault("pending_child_urls", [])
            cap = max(1, int(ctx.limits.get("max_manifest_urls", 250)))
            for child in child_urls[:cap]:
                pending.append({"url": child, "parent": rendered.final_url})
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


def _build_page(url: str, title: str, html: str) -> CollectedPage:
    md = dom_to_markdown(html)
    sections = split_sections(md) if md else []
    text = md or title
    lang = detect_language(url, text, declared=html_language(html))
    return CollectedPage(
        title=title or url,
        url=url,
        content=text,
        raw=html.encode("utf-8", errors="replace"),
        content_type="text/html",
        metadata={
            "content_markdown": text,
            "sections": sections,
            "language": lang,
            "page_title": title or url,
            "page_url": url,
            "rendered_via": "playwright",
        },
    )


def _filter_links(
    links: list[str],
    seed_url: str,
    seed_host: str,
    same_host: bool,
    tags: list[str],
) -> list[str]:
    seed_norm = seed_url.rstrip("/").lower()
    prefix = infer_path_prefix(seed_url)
    out: list[str] = []
    for link in links:
        if link.rstrip("/").lower() == seed_norm:
            continue
        if same_host and (urlparse(link).hostname or "").lower() != seed_host:
            continue
        if not keep_crawl_url(link, seed_url, prefix=prefix):
            continue
        if tags and not matches_topic_tags(tags, link):
            continue
        out.append(link)
    return out


def _fetch_child(url: str, ctx: ConnectorContext) -> CollectedPage | None:
    try:
        resp = ctx.client.get(url, use_cache=bool(ctx.limits.get("use_cache", True)))
        body = bytes(getattr(resp, "content", b"") or b"")
        html = body.decode(getattr(resp, "encoding", None) or "utf-8", errors="replace")
        final_url = str(getattr(resp, "url", url) or url)
        return _build_page(final_url, final_url.rsplit("/", 1)[-1] or final_url, html)
    except Exception:  # noqa: BLE001
        return None
