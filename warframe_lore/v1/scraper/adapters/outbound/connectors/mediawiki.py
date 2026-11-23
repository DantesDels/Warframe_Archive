"""MediaWiki API connector with generic discovery fallback."""

from __future__ import annotations

import json
from typing import Any, cast
from urllib.parse import ParseResult, parse_qs, urlparse

from ....collect.html_extract import html_title, html_to_text
from ....collect.http import bot_headers, browser_headers
from ....ports.outbound.sources import CollectedPage, ConnectorContext


class MediaWikiConnector:
    name = "mediawiki"
    kinds = ("wiki", "website")

    def can_handle(self, source: dict[str, Any], _ctx: ConnectorContext) -> bool:
        loc = str(source.get("location", ""))
        host = urlparse(loc).netloc.lower()
        return "wiki" in host and "/api.php" not in urlparse(loc).path

    def collect(
        self, source: dict[str, Any], ctx: ConnectorContext
    ) -> list[CollectedPage]:
        url = str(source.get("location", "")).strip()
        parsed = urlparse(url)
        api = f"{parsed.scheme}://{parsed.netloc}/api.php"
        max_pages = max(1, int(ctx.limits.get("max_pages_per_source", 1)))
        title = _title_from_url(parsed)
        pages = _extract(ctx, api, title)
        if pages:
            return pages[:max_pages]
        if max_pages <= 1:
            return [_single_html(ctx, url)]
        titles = _all_pages(ctx, api, max_pages)
        out: list[CollectedPage] = []
        for page_title in titles[:max_pages]:
            out.extend(_extract(ctx, api, page_title))
        return out or [_single_html(ctx, url)]


def _title_from_url(parsed: ParseResult) -> str:
    title_values = parse_qs(parsed.query).get("title", [])
    if title_values:
        return str(title_values[0])
    tail = parsed.path.rsplit("/", 1)[-1].replace("_", " ").strip()
    return tail or "Main Page"


def _single_html(ctx: ConnectorContext, url: str) -> CollectedPage:
    resp = ctx.client.get(url, headers=browser_headers(), use_cache=_cache(ctx))
    body = resp.content.decode(resp.encoding or "utf-8", errors="replace")
    return CollectedPage(
        html_title(body) or url,
        resp.url,
        html_to_text(body),
        from_cache=resp.from_cache,
        raw=resp.content,
    )


def _extract(ctx: ConnectorContext, api: str, title: str) -> list[CollectedPage]:
    params: dict[str, str | int] = {
        "action": "query",
        "prop": "extracts|info|revisions",
        "explaintext": 1,
        "inprop": "url",
        "rvprop": "ids|timestamp",
        "redirects": 1,
        "titles": title,
        "format": "json",
    }
    resp = _get(ctx, api, params)
    data = _json(resp.content)
    query = cast(dict[str, Any], data.get("query", {}))
    pages = cast(dict[str, Any], query.get("pages", {}))
    page = cast(dict[str, Any], next(iter(pages.values()), cast(dict[str, Any], {})))
    text = str(page.get("extract", "") or "").strip()
    revid = str(page.get("lastrevid") or "")
    touched = str(page.get("touched") or "")
    revs = page.get("revisions")
    if isinstance(revs, list) and revs and isinstance(revs[0], dict):
        revid = str(revs[0].get("revid") or revid)
        touched = str(revs[0].get("timestamp") or touched)
    marker = f"{revid}:{touched}" if (revid or touched) else ""
    state = _mw_state(ctx, api)
    incremental = bool(ctx.limits.get("incremental", True))
    page_key = str(page.get("pageid") or title)
    if incremental and marker and state.get(page_key) == marker:
        return []
    if marker:
        state[page_key] = marker
    if not text:
        return []
    return [
        CollectedPage(
            str(page.get("title", title)),
            str(page.get("fullurl", title)),
            text,
            from_cache=bool(resp.from_cache),
            raw=cast(bytes | None, resp.content),
            content_type=str(resp.content_type),
            metadata={"touched": touched, "revid": str(page.get("lastrevid", ""))},
        )
    ]


def _all_pages(ctx: ConnectorContext, api: str, max_pages: int) -> list[str]:
    titles: list[str] = []
    cont: str | None = None
    while len(titles) < max_pages:
        params: dict[str, str | int] = {
            "action": "query",
            "list": "allpages",
            "apnamespace": "0",
            "aplimit": str(min(50, max_pages - len(titles))),
            "format": "json",
        }
        if cont:
            params["apcontinue"] = cont
        data = _json(_get(ctx, api, params).content)
        query = cast(dict[str, Any], data.get("query", {}))
        allpages = cast(list[dict[str, Any]], query.get("allpages", []))
        for item in allpages:
            name = str(item.get("title", "") or "").strip()
            if name:
                titles.append(name)
        continue_info = cast(dict[str, Any], data.get("continue", {}))
        cont_val = continue_info.get("apcontinue")
        cont = str(cont_val) if cont_val else None
        if not cont:
            break
    return titles


def _get(ctx: ConnectorContext, api: str, params: dict[str, str | int]) -> Any:
    try:
        return ctx.client.get(
            api, headers=bot_headers(), params=params, use_cache=_cache(ctx)
        )
    except Exception:
        return ctx.client.get(
            api, headers=browser_headers(), params=params, use_cache=_cache(ctx)
        )


def _cache(ctx: ConnectorContext) -> bool:
    return bool(ctx.limits.get("use_cache", True))


def _mw_state(ctx: ConnectorContext, url: str) -> dict[str, str]:
    root = ctx.limits.setdefault("connector_state", {})
    bucket = root.setdefault("mediawiki", {})
    item = bucket.setdefault(url, {})
    return item  # type: ignore[return-value]


def _json(data: bytes) -> dict[str, Any]:
    parsed = json.loads(data.decode("utf-8", errors="replace"))
    if isinstance(parsed, dict):
        return cast(dict[str, Any], parsed)
    return {}
