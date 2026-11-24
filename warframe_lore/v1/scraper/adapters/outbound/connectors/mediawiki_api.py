"""MediaWiki API helpers (core client, allpages, and compatibility facade)."""

from __future__ import annotations

import json
from typing import Any, cast

from ....collect.http import bot_headers, browser_headers
from ....observability.progress import stop_requested
from ....ports.outbound.sources import CollectedPage, ConnectorContext


def wiki_state(ctx: ConnectorContext, url: str) -> dict[str, str]:
    """Return the incremental state bucket for one API endpoint."""
    root = ctx.limits.setdefault("connector_state", {})
    bucket = root.setdefault("mediawiki", {})
    return cast(dict[str, str], bucket.setdefault(url, {}))


def parse_json(data: bytes) -> dict[str, Any]:
    """Parse an API response into a typed mapping."""
    parsed = json.loads(data.decode("utf-8", errors="replace"))
    return cast(dict[str, Any], parsed) if isinstance(parsed, dict) else {}


def get_json(
    ctx: ConnectorContext, api: str, params: dict[str, str | int]
) -> Any:
    """Fetch JSON with a bot-agent fallback to browser headers."""
    kwargs = {
        "headers": bot_headers(),
        "params": params,
        "use_cache": bool(ctx.limits.get("use_cache", True)),
    }
    try:
        return ctx.client.get(api, **kwargs)
    except Exception:
        kwargs["headers"] = browser_headers()
        return ctx.client.get(api, **kwargs)


def extract_page(
    ctx: ConnectorContext, api: str, title: str
) -> list[CollectedPage]:
    """Fetch one article with categories, revision and structured Markdown."""
    from .wiki.batch import extract_pages_batch

    return extract_pages_batch(ctx, api, [title])


def all_pages(
    ctx: ConnectorContext, api: str, max_pages: int, *, prefix: str = ""
) -> list[str]:
    """List non-redirect article titles from the MediaWiki allpages API."""
    titles: list[str] = []
    continuation: str | None = None
    while len(titles) < max_pages and not stop_requested(ctx.limits):
        params: dict[str, str | int] = {
            "action": "query",
            "list": "allpages",
            "apnamespace": "0",
            "apfilterredir": "nonredirects",
            "aplimit": str(min(500, max(25, max_pages - len(titles)))),
            "format": "json",
        }
        if prefix:
            params["apprefix"] = prefix
        if continuation:
            params["apcontinue"] = continuation
        data = parse_json(get_json(ctx, api, params).content)
        query = cast(dict[str, Any], data.get("query", {}))
        entries = cast(list[dict[str, Any]], query.get("allpages", []))
        if not entries:
            break
        titles.extend(
            name for entry in entries
            if (name := str(entry.get("title", "") or "").strip())
        )
        cont = cast(dict[str, Any], data.get("continue", {}))
        continuation = str(cont.get("apcontinue") or "") or None
        if not continuation:
            break
    return titles
