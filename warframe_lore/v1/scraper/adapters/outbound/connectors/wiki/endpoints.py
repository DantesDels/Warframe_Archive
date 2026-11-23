"""MediaWiki API endpoint auto-discovery and siteinfo probing."""

from __future__ import annotations

from typing import cast
from urllib.parse import urlparse

from .....ports.outbound.sources import ConnectorContext
from ..mediawiki_api import get_json, parse_json

_WIKIMEDIA_HOSTS = (
    "wikipedia.org",
    "wiktionary.org",
    "wikibooks.org",
    "wikiquote.org",
    "wikisource.org",
    "wikiversity.org",
    "wikimedia.org",
)


def resolve_api(ctx: ConnectorContext, url: str) -> tuple[str, str]:
    """Return (api_endpoint, main_page_title), cached per host."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if parsed.path.rstrip("/").endswith("/api.php"):
        return url.split("?", 1)[0], "Main Page"
    cache = _api_cache(ctx)
    if base in cache:
        return cache[base]
    candidates = _candidate_endpoints(base, parsed.netloc.lower())
    for endpoint in candidates:
        main_page = _probe_siteinfo(ctx, endpoint)
        if main_page is not None:
            cache[base] = (endpoint, main_page)
            return endpoint, main_page
    fallback = (candidates[0], "Main Page")
    cache[base] = fallback
    return fallback


def _candidate_endpoints(base: str, host: str) -> list[str]:
    is_wm = any(host == s or host.endswith(f".{s}") for s in _WIKIMEDIA_HOSTS)
    if is_wm:
        return [f"{base}/w/api.php", f"{base}/api.php"]
    return [f"{base}/api.php", f"{base}/w/api.php", f"{base}/wiki/api.php"]


def _probe_siteinfo(ctx: ConnectorContext, endpoint: str) -> str | None:
    params: dict[str, str | int] = {
        "action": "query",
        "meta": "siteinfo",
        "siprop": "general",
        "format": "json",
    }
    try:
        resp = get_json(ctx, endpoint, params)
    except Exception:
        return None
    if int(getattr(resp, "status", 200)) >= 400:
        return None
    data = parse_json(bytes(getattr(resp, "content", b"")))
    query = data.get("query")
    if not isinstance(query, dict):
        return None
    general = query.get("general")
    if isinstance(general, dict) and general.get("mainpage"):
        return str(general["mainpage"])
    return "Main Page"


def _api_cache(ctx: ConnectorContext) -> dict[str, tuple[str, str]]:
    root = ctx.limits.setdefault("connector_state", {})
    return cast(dict[str, tuple[str, str]], root.setdefault("mediawiki_apis", {}))
