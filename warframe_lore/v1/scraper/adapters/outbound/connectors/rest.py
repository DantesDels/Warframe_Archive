"""Generic REST/JSON connector with pagination/cursor support."""

from __future__ import annotations

from typing import Any, cast
from urllib.parse import urljoin

from ....ports.outbound.sources import CollectedPage, ConnectorContext


class RestConnector:
    name = "rest"
    kinds = ("api", "rest", "graphql")

    def can_handle(self, source: dict[str, Any], _ctx: ConnectorContext) -> bool:
        kind = str(source.get("kind", "")).lower()
        loc = str(source.get("location", "")).lower()
        return (
            kind in {"api", "rest", "graphql"}
            or "/graphql" in loc
            or loc.endswith(".json")
        )

    def collect(self, source: dict[str, Any],
        ctx: ConnectorContext) -> list[CollectedPage]:
        url = str(source.get("location", "")).strip()
        headers = cast(dict[str, str], dict(source.get("headers", {}) or {}))
        auth = source.get("auth")
        if isinstance(auth, dict):
            if auth.get("bearer"):
                headers["Authorization"] = f"Bearer {auth['bearer']}"
            if auth.get("header") and auth.get("value"):
                headers[str(auth["header"])] = str(auth["value"])
        pages: list[CollectedPage] = []
        next_url: str | None = url
        seen: set[str] = set()
        max_pages = max(1, int(ctx.limits.get("max_pages_per_source", 25)))
        while next_url and len(pages) < max_pages and next_url not in seen:
            seen.add(next_url)
            resp = ctx.client.get(
                next_url,
                headers=headers,
                use_cache=bool(ctx.limits.get("use_cache", True)),
            )
            data = _json(bytes(getattr(resp, "content", b"")))
            items = _items(data)
            if not items:
                items = [data]
            for i, item in enumerate(items):
                if len(pages) >= max_pages:
                    break
                title = str(
                    item.get("title")
                    or item.get("name")
                    or item.get("id")
                    or f"item-{i}"
                )
                link = str(item.get("url") or item.get("link") or next_url)
                pages.append(
                    CollectedPage(
                        title=title,
                        url=link,
                        content=_text(item),
                        metadata={"source_api": next_url},
                    )
                )
            next_url = _next(data, next_url)
        return pages


def _json(body: bytes) -> dict[str, Any]:
    import json

    try:
        parsed = json.loads(body.decode("utf-8", errors="replace"))
    except Exception:
        return {"raw": body.decode("utf-8", errors="replace")}
    if isinstance(parsed, dict):
        return cast(dict[str, Any], parsed)
    if isinstance(parsed, list):
        return {"items": parsed}
    return {"value": parsed}


def _items(data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("items", "data", "results", "records"):
        val = data.get(key)
        if isinstance(val, list):
            return [cast(dict[str, Any], v) for v in val if isinstance(v, dict)]
    return []


def _next(data: dict[str, Any], current: str) -> str | None:
    for key in ("next", "next_url", "nextPage", "next_cursor_url"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return urljoin(current, val.strip())
    page_info = data.get("pageInfo")
    if isinstance(page_info, dict):
        cursor = page_info.get("endCursor") or page_info.get("nextCursor")
        if cursor and "cursor=" not in current:
            sep = "&" if "?" in current else "?"
            return f"{current}{sep}cursor={cursor}"
    return None


def _text(item: dict[str, Any]) -> str:
    for key in ("content", "text", "body", "summary", "description"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return str({k: item[k] for k in list(item.keys())[:20]})
