"""Generic MediaWiki API connector with auto-API, batching and category crawl."""

from __future__ import annotations

from typing import Any
from urllib.parse import ParseResult, parse_qs, unquote, urlparse

from ....observability.progress import current_reporter, stop_requested
from ....ports.outbound.sources import CollectedPage, ConnectorContext
from .html import collect_html
from .mediawiki_api import all_pages, extract_page
from .wiki.batch import BATCH_SIZE, extract_pages_batch, filter_changed_titles
from .wiki.endpoints import resolve_api
from .wiki.listing import is_category_title, mainpage_links
from .wiki.search import titles_for_categories, titles_for_tags

_ROOT_TITLES = frozenset({
    "",
    "main page",
    "accueil",
    "home",
    "index",
    "wiki",
    "w",
})


class MediaWikiConnector:
    name = "mediawiki"
    kinds = ("wiki", "website", "api")

    def can_handle(self, source: dict[str, Any], _ctx: ConnectorContext) -> bool:
        parsed = urlparse(str(source.get("location", "")))
        return (
            str(source.get("kind", "")).lower() == "wiki"
            or "wiki" in parsed.netloc.lower()
            or parsed.path.rstrip("/").endswith("/api.php")
        )

    def collect(
        self, source: dict[str, Any], ctx: ConnectorContext
    ) -> list[CollectedPage]:
        url = str(source.get("location", "")).strip()
        api, main_page = resolve_api(ctx, url)
        max_pages = max(1, int(ctx.limits.get("max_pages_per_source", 1)))
        target = _title_from_url(urlparse(url))
        if _is_specific_article(target, main_page) and not source.get("categories"):
            pages = extract_page(ctx, api, target)
            return pages[:max_pages] if pages else _fallback(ctx, url)
        titles = _discover_titles(ctx, api, source, target, main_page, max_pages)
        if not titles:
            return _fallback(ctx, url)
        return _fetch_in_batches(ctx, api, titles[:max_pages]) or _fallback(ctx, url)


def _discover_titles(
    ctx: ConnectorContext, api: str, source: dict[str, Any],
    target: str, main_page: str, max_pages: int,
) -> list[str]:
    cats = [str(c) for c in (source.get("categories") or []) if str(c).strip()]
    if is_category_title(target) and target not in cats:
        cats.insert(0, target)
    depth = max(0, int(ctx.limits.get("max_depth", 2)))
    if cats:
        return titles_for_categories(ctx, api, cats, max_pages, depth)
    raw_tags = ctx.limits.get("topic_tags") or []
    tags = [str(t).strip() for t in raw_tags if str(t).strip()]
    if tags:
        return titles_for_tags(ctx, api, tags, max_pages, depth)
    prefix = str(source.get("prefix") or "")
    titles: list[str] = []
    if not prefix:
        titles.extend(mainpage_links(ctx, api, main_page, min(max_pages, 200)))
    if len(titles) < max_pages:
        seen = set(titles)
        for name in all_pages(ctx, api, max_pages, prefix=prefix):
            if name not in seen:
                seen.add(name)
                titles.append(name)
                if len(titles) >= max_pages:
                    break
    return titles


def _fetch_in_batches(
    ctx: ConnectorContext, api: str, titles: list[str]
) -> list[CollectedPage]:
    to_fetch = filter_changed_titles(ctx, api, titles)
    reporter = current_reporter(ctx.limits)
    collected: list[CollectedPage] = []
    total = len(to_fetch)
    for offset in range(0, total, BATCH_SIZE):
        if stop_requested(ctx.limits):
            break
        batch = to_fetch[offset : offset + BATCH_SIZE]
        collected.extend(extract_pages_batch(ctx, api, batch))
        reporter.page(min(offset + len(batch), total), total, batch[-1])
    return collected


def _title_from_url(parsed: ParseResult) -> str:
    title_values = parse_qs(parsed.query).get("title", [])
    if title_values:
        return unquote(str(title_values[0])).replace("_", " ").strip()
    path = parsed.path.rstrip("/")
    if not path or path.endswith("/api.php"):
        return ""
    return unquote(path.rsplit("/", 1)[-1]).replace("_", " ").strip()


def _is_specific_article(target: str, main_page: str) -> bool:
    low = target.strip().lower()
    if low in _ROOT_TITLES or low == main_page.strip().lower():
        return False
    return not is_category_title(target)


def _fallback(ctx: ConnectorContext, url: str) -> list[CollectedPage]:
    limits = {**ctx.limits, "max_pages_per_source": 1}
    single = ConnectorContext(
        client=ctx.client, limits=limits, capabilities=ctx.capabilities
    )
    return collect_html(url, single)
