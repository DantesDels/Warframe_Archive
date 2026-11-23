"""Convert one raw MediaWiki API page payload into a CollectedPage."""

from __future__ import annotations

from typing import Any, cast

from .....collect.wikitext import page_metadata, wikitext_to_markdown
from .....ports.outbound.sources import CollectedPage


def iter_pages(raw: Any) -> list[dict[str, Any]]:
    """Normalize formatversion=1 dicts and formatversion=2 lists."""
    if isinstance(raw, dict):
        return [p for p in raw.values() if isinstance(p, dict)]
    if isinstance(raw, list):
        return [p for p in raw if isinstance(p, dict)]
    return []


def build_page(
    page: dict[str, Any],
    api: str,
    state: dict[str, str],
    incremental: bool,
    from_cache: bool,
) -> CollectedPage | None:
    """Build a structured CollectedPage or return None if unchanged/empty."""
    revisions = cast(list[dict[str, Any]], page.get("revisions") or [])
    revision = revisions[0] if revisions else {}
    slots = cast(dict[str, Any], revision.get("slots") or {})
    main = cast(dict[str, Any], slots.get("main") or {})
    wikitext = str(main.get("*") or main.get("content") or "")
    touched = str(revision.get("timestamp") or page.get("touched") or "")
    revid = str(revision.get("revid") or page.get("lastrevid") or "")
    marker = f"{revid}:{touched}"
    name = str(page.get("title", "") or "").strip()
    page_key = str(page.get("pageid") or name)
    if incremental and marker and state.get(page_key) == marker:
        return None
    if marker:
        state[page_key] = marker
    markdown = (
        wikitext_to_markdown(wikitext) if wikitext
        else str(page.get("extract", "") or "").strip()
    )
    if not markdown or not name:
        return None
    url = str(page.get("fullurl") or _wiki_url(api, name))
    raw_cats = cast(list[dict[str, Any]], page.get("categories") or [])
    cats = [
        str(e.get("title", "")).split(":", 1)[-1]
        for e in raw_cats if isinstance(e, dict)
    ]
    meta = page_metadata(name, url, api, cats, touched, revid, markdown, wikitext)
    return CollectedPage(
        name, url, markdown, from_cache=from_cache,
        content_type="text/markdown", metadata=meta,
    )


def _wiki_url(api: str, title: str) -> str:
    base = api.split("/w/api.php")[0].split("/api.php")[0]
    return f"{base}/wiki/{title.replace(' ', '_')}"
