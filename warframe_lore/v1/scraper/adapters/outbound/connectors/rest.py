"""Generic REST/JSON connector with pagination/cursor support."""

from __future__ import annotations

import re
from typing import Any, cast
from urllib.parse import parse_qs, urljoin, urlparse

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
        headers = _headers(source)
        pages: list[CollectedPage] = []
        next_url: str | None = url
        seen: set[str] = set()
        max_pages = max(1, int(ctx.limits.get("max_pages_per_source", 25)))
        method = str(source.get("method", "GET")).upper()
        body = source.get("body") if isinstance(source.get("body"), dict) else None
        while next_url and len(pages) < max_pages and next_url not in seen:
            seen.add(next_url)
            resp = _request(ctx, next_url, headers, method=method, body=body)
            data = _json(bytes(getattr(resp, "content", b"")))
            items = _items(data) or [data]
            for i, item in enumerate(items):
                if len(pages) >= max_pages:
                    break
                title = str(item.get("title") or item.get("name")
                            or item.get("id") or f"item-{i}")
                link = str(item.get("url") or item.get("link")
                           or item.get("html_url") or next_url)
                pages.append(CollectedPage(
                    title=title, url=link, content=_text(item),
                    metadata={"source_api": next_url, "connector": "rest"},
                ))
            next_url = _next(data, next_url, getattr(resp, "headers", {}) or {})
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
        r = requests.post(url, headers=headers, json=body, timeout=25)
        return type("R", (), {"content": r.content,
                              "headers": dict(r.headers),
                              "status": r.status_code})()
    return client.get(url, headers=headers, use_cache=use_cache)


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
    for key in ("items", "data", "results", "records", "edges", "nodes"):
        val = data.get(key)
        if isinstance(val, dict):
            for k2 in ("items", "nodes", "edges", "results"):
                v2 = val.get(k2)
                if isinstance(v2, list):
                    val = v2
                    break
        if isinstance(val, list):
            out = []
            for v in val:
                if isinstance(v, dict) and "node" in v and isinstance(v["node"], dict):
                    out.append(cast(dict[str, Any], v["node"]))
                elif isinstance(v, dict):
                    out.append(cast(dict[str, Any], v))
            if out:
                return out
    return []


def _next(data: dict[str, Any], current: str,
           headers: dict[str, str] | Any) -> str | None:
    link = None
    if isinstance(headers, dict):
        link = headers.get("Link") or headers.get("link")
    if isinstance(link, str):
        m = re.search(r"<([^>]+)>;\s*rel=\"?next\"?", link)
        if m:
            return urljoin(current, m.group(1))
    for key in ("next", "next_url", "nextPage", "next_cursor_url", "nextLink"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return urljoin(current, val.strip())
    page_info = data.get("pageInfo")
    if isinstance(page_info, dict):
        if page_info.get("hasNextPage") is False:
            return None
        cursor = page_info.get("endCursor") or page_info.get("nextCursor")
        if cursor:
            parsed = urlparse(current)
            qs = parse_qs(parsed.query)
            for k in ("cursor", "after", "pageToken", "page_token"):
                if k in qs:
                    qs[k] = [str(cursor)]
                    query = "&".join(f"{kk}={vv[0]}" for kk, vv in qs.items())
                    return parsed._replace(query=query).geturl()
            sep = "&" if parsed.query else "?"
            return f"{current}{sep}cursor={cursor}"
    return None


def _text(item: dict[str, Any]) -> str:
    for key in ("content", "text", "body", "summary", "description", "extract"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return str({k: item[k] for k in list(item.keys())[:20]})
