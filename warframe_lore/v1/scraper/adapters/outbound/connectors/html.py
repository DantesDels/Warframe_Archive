"""Generic HTML crawl connector with Markdown sections and noise filtering."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ....collect.crawl_filter import (
    infer_path_prefix,
    keep_crawl_url,
    matches_topic_tags,
)
from ....collect.dom_clean import html_language
from ....collect.html_extract import extract_links, html_title, markdown_to_text
from ....collect.http import browser_headers
from ....collect.language import detect_language
from ....collect.wikitext import split_sections
from ....observability.progress import current_reporter, stop_requested
from ....ports.outbound.sources import CollectedPage, ConnectorContext


class HtmlConnector:
    name = "html"
    kinds = ("website", "api", "wiki")

    def can_handle(self, _source: dict[str, Any], _ctx: ConnectorContext) -> bool:
        return True

    def collect(
        self, source: dict[str, Any], ctx: ConnectorContext
    ) -> list[CollectedPage]:
        url = str(source.get("location", "")).strip()
        prefix = infer_path_prefix(url, str(source.get("path_prefix") or ""))
        excludes = tuple(str(x) for x in (source.get("exclude_paths") or ()))
        cfg = source.get("config") if isinstance(source.get("config"), dict) else {}
        selector = str(cfg.get("contentSelector") or "").strip()
        return collect_html(
            url, ctx, path_prefix=prefix, extra_excludes=excludes,
            content_selector=selector,
        )


def collect_html(
    url: str, ctx: ConnectorContext, *, path_prefix: str = "",
    extra_excludes: tuple[str, ...] = (), content_selector: str = "",
) -> list[CollectedPage]:
    limits = ctx.limits
    max_pages = max(1, int(limits.get("max_pages_per_source", 1)))
    max_depth = max(0, int(limits.get("max_depth", 0)))
    same_host = bool(limits.get("same_host_only", True))
    use_cache = bool(limits.get("use_cache", True))
    prefix = path_prefix or infer_path_prefix(url)
    tags = [str(t).strip() for t in (limits.get("topic_tags") or []) if str(t).strip()]
    queue: list[tuple[str, int]] = [(url, 0)]
    seen: set[str] = set()
    pages: list[CollectedPage] = []
    reporter = current_reporter(limits)
    while queue and len(pages) < max_pages:
        if stop_requested(limits):
            reporter.skip("Crawl interrompu", url)
            break
        current, depth = queue.pop(0)
        norm = current.rstrip("/")
        if norm in seen:
            continue
        seen.add(norm)
        resp, err = _fetch_html(ctx, current, use_cache)
        if resp is None:
            if depth == 0 and not pages and err is not None:
                raise err
            if err is not None:
                reporter.skip(f"Erreur HTTP ({type(err).__name__})", current)
            continue
        final_url = str(getattr(resp, "url", "") or current)
        if depth > 0 and not keep_crawl_url(
            final_url, url, prefix=prefix, extra_excludes=extra_excludes
        ):
            continue
        page, html_body = _build_page(resp, content_selector=content_selector)
        ok_tag = matches_topic_tags(tags, page.url, page.title, page.content[:2000])
        if depth == 0 or ok_tag:
            pages.append(page)
            reporter.page(len(pages), max_pages, str(resp.url))
        if depth >= max_depth or not html_body:
            continue
        for link in extract_links(html_body, str(resp.url), same_host=same_host):
            if link.rstrip("/") in seen:
                continue
            if keep_crawl_url(link, url, prefix=prefix, extra_excludes=extra_excludes):
                idx = 0 if (tags and matches_topic_tags(tags, link)) else len(queue)
                queue.insert(idx, (link, depth + 1))
    return pages


def _fetch_html(
    ctx: ConnectorContext, url: str, use_cache: bool
) -> tuple[Any | None, Exception | None]:
    try:
        return ctx.client.get(url, headers=browser_headers(), use_cache=use_cache), None
    except Exception as exc:  # noqa: BLE001
        return None, exc


def _build_page(
    resp: Any, *, content_selector: str = ""
) -> tuple[CollectedPage, str]:
    ctype = str(getattr(resp, "content_type", "") or "").lower()
    raw = bytes(getattr(resp, "content", b""))
    body = raw.decode(getattr(resp, "encoding", None) or "utf-8", errors="replace")
    resp_url = str(getattr(resp, "url", ""))
    from_cache = bool(getattr(resp, "from_cache", False))
    if "html" not in ctype and "<html" not in body.lower():
        parsed = urlparse(resp_url)
        return CollectedPage(
            title=Path(parsed.path).name or parsed.netloc, url=resp_url,
            content=body, from_cache=from_cache, raw=raw, content_type=ctype,
        ), ""
    title = html_title(body) or urlparse(resp_url).netloc
    markdown = _extract_markdown(body, content_selector)
    meta = {
        "language": detect_language(resp_url, markdown, html_language(body)),
        "content_markdown": markdown, "sections": split_sections(title, markdown),
        "page_title": title, "page_url": resp_url,
    }
    page = CollectedPage(
        title=title, url=resp_url, content=markdown,
        from_cache=from_cache, raw=raw, content_type=ctype, metadata=meta,
    )
    return page, body


def _extract_markdown(html_body: str, selector: str) -> str:
    if selector:
        from ....self_heal.sandbox import extract_with_selector

        return extract_with_selector(html_body, selector) or markdown_to_text(html_body)
    return markdown_to_text(html_body)
