"""Batched incremental MediaWiki page fetching and lightweight delta filter."""

from __future__ import annotations

from typing import Any, cast

from .....observability.progress import stop_requested
from .....ports.outbound.sources import CollectedPage, ConnectorContext
from ..mediawiki_api import get_json, parse_json, wiki_state
from .page_builder import build_page, iter_pages

BATCH_SIZE = 20
INFO_BATCH_SIZE = 50


def extract_pages_batch(
    ctx: ConnectorContext, api: str, titles: list[str]
) -> list[CollectedPage]:
    """Fetch up to BATCH_SIZE articles in a single MediaWiki API query."""
    if not titles:
        return []
    params: dict[str, str | int] = {
        "action": "query",
        "prop": "extracts|info|revisions|categories",
        "explaintext": 1,
        "inprop": "url",
        "rvprop": "ids|timestamp|content",
        "rvslots": "main",
        "cllimit": "max",
        "redirects": 1,
        "titles": "|".join(titles),
        "format": "json",
    }
    response = get_json(ctx, api, params)
    query = cast(dict[str, Any], parse_json(response.content).get("query", {}))
    state = wiki_state(ctx, api)
    incremental = bool(ctx.limits.get("incremental", True))
    from_cache = bool(getattr(response, "from_cache", False))
    pages: list[CollectedPage] = []
    for entry in iter_pages(query.get("pages", {})):
        if entry.get("missing") is not None:
            continue
        built = build_page(entry, api, state, incremental, from_cache)
        if built is not None:
            pages.append(built)
    return pages


def filter_changed_titles(
    ctx: ConnectorContext, api: str, titles: list[str]
) -> list[str]:
    """Pre-filter titles with lightweight prop=info batches before full fetch."""
    state = wiki_state(ctx, api)
    if not bool(ctx.limits.get("incremental", True)) or not state:
        return titles
    changed: list[str] = []
    for offset in range(0, len(titles), INFO_BATCH_SIZE):
        if stop_requested(ctx.limits):
            break
        chunk = titles[offset : offset + INFO_BATCH_SIZE]
        changed.extend(_check_chunk(ctx, api, chunk, state))
    return changed


def _check_chunk(
    ctx: ConnectorContext, api: str, chunk: list[str], state: dict[str, str]
) -> list[str]:
    params: dict[str, str | int] = {
        "action": "query",
        "prop": "info",
        "inprop": "url",
        "redirects": 1,
        "titles": "|".join(chunk),
        "format": "json",
    }
    try:
        data = parse_json(get_json(ctx, api, params).content)
    except Exception:
        return list(chunk)
    query = cast(dict[str, Any], data.get("query", {}))
    out: list[str] = []
    for page in iter_pages(query.get("pages", {})):
        if page.get("missing") is not None:
            continue
        name = str(page.get("title", "") or "").strip()
        key = str(page.get("pageid") or name)
        marker = f"{page.get('lastrevid', '')}:{page.get('touched', '')}"
        if name and (not marker or state.get(key) != marker):
            out.append(name)
    return out
