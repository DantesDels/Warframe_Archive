"""MediaWiki title discovery: hub links, recursive categories, and allpages."""

from __future__ import annotations

from typing import Any, cast

from .....observability.progress import stop_requested
from .....ports.outbound.sources import ConnectorContext
from ..mediawiki_api import get_json, parse_json

_CATEGORY_PREFIXES = (
    "category:",
    "catégorie:",
    "categorie:",
    "kategorie:",
    "categoría:",
)
_SKIP_SUBCAT_TOKENS = (
    "mods", "skins", "cosmetics", "glyphs", "sigils", "emotes", "palettes",
    "bundles", "patch history", "update ", "stubs", "disambiguation",
    "templates", "files", "images", "videos", "audio", "users", "blog",
    "quest items", "quest rewards", "weapons",
)
_SKIP_TITLE_SUFFIXES = ("/patch history", "/media", "/main", "/sectionlist")


def is_category_title(title: str) -> bool:
    """Return True when ``title`` names a MediaWiki category."""
    return title.strip().lower().startswith(_CATEGORY_PREFIXES)


def mainpage_links(
    ctx: ConnectorContext, api: str, title: str, limit: int
) -> list[str]:
    """Return namespace-0 linked titles from a hub or main page."""
    if not title or limit <= 0:
        return []
    params: dict[str, str | int] = {
        "action": "query",
        "prop": "links",
        "titles": title,
        "plnamespace": "0",
        "pllimit": str(min(500, limit)),
        "format": "json",
    }
    try:
        data = parse_json(get_json(ctx, api, params).content)
    except Exception:
        return []
    query = cast(dict[str, Any], data.get("query", {}))
    out: list[str] = []
    for page in _iter_pages(query.get("pages", {})):
        for link in cast(list[dict[str, Any]], page.get("links") or []):
            name = str(link.get("title", "") or "").strip()
            if name and name not in out:
                out.append(name)
                if len(out) >= limit:
                    return out
    return out


def category_members(
    ctx: ConnectorContext,
    api: str,
    category: str,
    max_pages: int,
    *,
    max_depth: int = 2,
) -> list[str]:
    """Recursively list namespace-0 titles belonging to ``category``."""
    seen_cats: set[str] = set()
    titles: list[str] = []
    seen: set[str] = set()
    clean = category.strip()
    start = clean if is_category_title(clean) else f"Category:{clean}"
    queue: list[tuple[str, int]] = [(start, 0)]
    while queue and len(titles) < max_pages and not stop_requested(ctx.limits):
        cat, depth = queue.pop(0)
        if cat.lower() in seen_cats:
            continue
        seen_cats.add(cat.lower())
        _walk_category(ctx, api, cat, depth, max_depth, max_pages, titles, seen, queue)
    return titles


def _walk_category(
    ctx: ConnectorContext,
    api: str,
    cat: str,
    depth: int,
    max_depth: int,
    max_pages: int,
    titles: list[str],
    seen: set[str],
    queue: list[tuple[str, int]],
) -> None:
    cont: str | None = None
    while len(titles) < max_pages and not stop_requested(ctx.limits):
        params: dict[str, str | int] = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": cat,
            "cmlimit": str(min(500, max_pages - len(titles) + 50)),
            "format": "json",
        }
        if cont:
            params["cmcontinue"] = cont
        data = parse_json(get_json(ctx, api, params).content)
        query = cast(dict[str, Any], data.get("query", {}))
        members = cast(list[dict[str, Any]], query.get("categorymembers", []))
        for item in members:
            ns = int(item.get("ns", 0) or 0)
            name = str(item.get("title", "") or "").strip()
            low = name.lower()
            if ns == 0 and name and name not in seen and not low.endswith(
                _SKIP_TITLE_SUFFIXES
            ):
                seen.add(name)
                titles.append(name)
                if len(titles) >= max_pages:
                    return
            elif (
                ns == 14
                and depth < min(max_depth, 2)
                and name
                and not any(tok in low for tok in _SKIP_SUBCAT_TOKENS)
            ):
                queue.append((name, depth + 1))
        cont_map = cast(dict[str, Any], data.get("continue", {}))
        cont = str(cont_map.get("cmcontinue") or "") or None
        if not cont:
            break


def _iter_pages(pages: Any) -> list[dict[str, Any]]:
    if isinstance(pages, dict):
        return [p for p in pages.values() if isinstance(p, dict)]
    if isinstance(pages, list):
        return [p for p in pages if isinstance(p, dict)]
    return []
