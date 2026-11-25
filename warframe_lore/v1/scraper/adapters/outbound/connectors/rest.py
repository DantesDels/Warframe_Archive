"""Generic REST/JSON connector with pagination/cursor support."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from ....observability.network import HTTP_TIMEOUT
from ....observability.progress import stop_requested
from ....ports.outbound.sources import CollectedPage, ConnectorContext
from .rest_parsing import (
    extract_items as _items,
)
from .rest_parsing import (
    item_text as _text,
)
from .rest_parsing import (
    next_url as _next,
)
from .rest_parsing import (
    parse_json as _json,
)


class RestConnector:
    name = "rest"
    kinds = ("api", "rest", "graphql")

    def can_handle(self, source: dict[str, Any], _ctx: ConnectorContext) -> bool:
        kind = str(source.get("kind", "")).lower()
        location = str(source.get("location", "")).lower()
        return (
            kind in {"api", "rest", "graphql"}
            or "/graphql" in location
            or location.endswith(".json")
            or ".json!" in location
        )

    def collect(self, source: dict[str, Any],
                ctx: ConnectorContext) -> list[CollectedPage]:
        url = str(source.get("location", "")).strip()
        headers = _headers(source)
        pages: list[CollectedPage] = []
        next_link: str | None = url
        seen: set[str] = set()
        max_pages = max(1, int(ctx.limits.get("max_pages_per_source", 25)))
        method = str(source.get("method", "GET")).upper()
        body = source.get("body") if isinstance(source.get("body"), dict) else None
        while next_link and len(pages) < max_pages and next_link not in seen:
            if stop_requested(ctx.limits):
                break
            seen.add(next_link)
            response = _request(ctx, next_link, headers, method=method, body=body)
            data = _json(bytes(getattr(response, "content", b"")))
            items = _items(data) or [data]
            res_name = Path(urlparse(next_link).path).name or "resource"
            cat = res_name.split("!", 1)[0].split("_", 1)[0].split(".", 1)[0]
            is_exp = cat.startswith("Export")
            for index, item in enumerate(items):
                if len(pages) >= max_pages:
                    break
                if is_exp and not (item.get("name") and item.get("description")):
                    continue
                text_body = _text(item)
                if not text_body:
                    continue
                fallback = res_name if len(items) == 1 else f"{res_name} #{index + 1}"
                title = str(
                    item.get("title") or item.get("name")
                    or item.get("uniqueName") or item.get("id") or fallback
                )
                if title.startswith("/Lotus/"):
                    continue
                raw_link = item.get("url") or item.get("link") or item.get("html_url")
                anchor = item.get("uniqueName") or item.get("id") or (index + 1)
                default_link = next_link if len(items) == 1 else f"{next_link}#{anchor}"
                link = str(raw_link or default_link)
                meta = {"source_api": next_link, "connector": "rest", "category": cat}
                page = CollectedPage(
                    title=title, url=link, content=text_body, metadata=meta
                )
                pages.append(page)
            next_link = _next(data, next_link, getattr(response, "headers", {}) or {})
            method, body = "GET", None
        return pages


def _headers(source: dict[str, Any]) -> dict[str, str]:
    headers = cast(dict[str, str], dict(source.get("headers", {}) or {}))
    auth = source.get("auth")
    if isinstance(auth, dict):
        if auth.get("bearer"):
            headers.setdefault("Authorization", f"Bearer {auth['bearer']}")
        if auth.get("header") and auth.get("value"):
            headers[str(auth["header"])] = str(auth["value"])
    return headers


def _request(ctx: ConnectorContext, url: str, headers: dict[str, str], *,
             method: str, body: dict[str, Any] | None) -> Any:
    client = ctx.client
    use_cache = bool(ctx.limits.get("use_cache", True))
    if method == "POST" and hasattr(client, "post"):
        return client.post(url, headers=headers, json=body, use_cache=use_cache)
    if method == "POST":
        import requests

        response = requests.post(url, headers=headers, json=body,
                                 timeout=HTTP_TIMEOUT)
        return type("R", (), {
            "content": response.content,
            "headers": dict(response.headers),
            "status": response.status_code,
        })()
    return client.get(url, headers=headers, use_cache=use_cache)
