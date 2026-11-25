"""Topic-tag search and category resolution for MediaWiki sources."""

from __future__ import annotations

from typing import Any, cast

from .....collect.crawl_filter import is_generalist_domain, matches_universe_topic
from .....ports.outbound.sources import ConnectorContext
from ..mediawiki_api import get_json, parse_json
from .listing import category_members


def search_titles(
    ctx: ConnectorContext, api: str, query_text: str, limit: int
) -> list[str]:
    """Return namespace-0 titles matching a topic tag via MediaWiki search."""
    if not query_text.strip() or limit <= 0:
        return []
    gen = is_generalist_domain(api)
    params: dict[str, str | int] = {
        "action": "query",
        "list": "search",
        "srnamespace": "0",
        "srsearch": query_text.strip(),
        "srlimit": str(min(50, limit * 4 if gen else limit)),
        "format": "json",
    }
    try:
        data = parse_json(get_json(ctx, api, params).content)
    except Exception:
        return []
    query = cast(dict[str, Any], data.get("query", {}))
    hits = cast(list[dict[str, Any]], query.get("search", []))
    raw_titles = [
        str(h["title"]).strip()
        for h in hits if isinstance(h, dict) and h.get("title")
    ]
    if not gen:
        return raw_titles[:limit]
    u_kw = [query_text.strip(), *(ctx.limits.get("universe_keywords") or ())]
    out = [
        t for t in raw_titles
        if matches_universe_topic(t, t, u_kw)
        and "(disambiguation)" not in t.lower()
        and not t.lower().startswith("list of ")
    ]
    return out[:limit]


def titles_for_categories(
    ctx: ConnectorContext, api: str, cats: list[str], max_pages: int, depth: int
) -> list[str]:
    """Collect deduplicated article titles across multiple categories."""
    out: list[str] = []
    seen: set[str] = set()
    for cat in cats:
        remaining = max_pages - len(out)
        for title in category_members(ctx, api, cat, remaining, max_depth=depth):
            if title not in seen:
                seen.add(title)
                out.append(title)
        if len(out) >= max_pages:
            break
    return out


def titles_for_tags(
    ctx: ConnectorContext, api: str, tags: list[str], max_pages: int, depth: int
) -> list[str]:
    """Resolve topic tags via exact categories first, then full-text search."""
    out = titles_for_categories(ctx, api, tags, max_pages, depth)
    seen = set(out)
    for tag in tags:
        if len(out) >= max_pages:
            break
        for title in search_titles(ctx, api, tag, max_pages - len(out)):
            if title not in seen:
                seen.add(title)
                out.append(title)
    return out[:max_pages]
