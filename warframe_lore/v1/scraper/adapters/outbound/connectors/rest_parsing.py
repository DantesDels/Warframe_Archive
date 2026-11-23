"""JSON payload parsing helpers for the generic REST connector."""

from __future__ import annotations

import json
import re
from typing import Any, cast
from urllib.parse import parse_qs, urljoin, urlparse


def parse_json(body: bytes) -> dict[str, Any]:
    decoded = body.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(decoded)
    except Exception:
        return {"raw": decoded}
    if isinstance(parsed, dict):
        return cast(dict[str, Any], parsed)
    if isinstance(parsed, list):
        return {"items": parsed}
    return {"value": parsed}


def extract_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("items", "data", "results", "records", "edges", "nodes"):
        value = data.get(key)
        if isinstance(value, dict):
            for nested_key in ("items", "nodes", "edges", "results"):
                nested = value.get(nested_key)
                if isinstance(nested, list):
                    value = nested
                    break
        if isinstance(value, list):
            items = []
            for item in value:
                if isinstance(item, dict) and isinstance(item.get("node"), dict):
                    items.append(cast(dict[str, Any], item["node"]))
                elif isinstance(item, dict):
                    items.append(cast(dict[str, Any], item))
            if items:
                return items
    return []


def next_url(
    data: dict[str, Any], current: str, headers: dict[str, str] | Any
) -> str | None:
    link = None
    if isinstance(headers, dict):
        link = headers.get("Link") or headers.get("link")
    if isinstance(link, str):
        match = re.search(r"<([^>]+)>;\s*rel=\"?next\"?", link)
        if match:
            return urljoin(current, match.group(1))
    for key in ("next", "next_url", "nextPage", "next_cursor_url", "nextLink"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return urljoin(current, value.strip())
    page_info = data.get("pageInfo")
    if not isinstance(page_info, dict):
        return None
    if page_info.get("hasNextPage") is False:
        return None
    cursor = page_info.get("endCursor") or page_info.get("nextCursor")
    if not cursor:
        return None
    parsed = urlparse(current)
    query = parse_qs(parsed.query)
    for key in ("cursor", "after", "pageToken", "page_token"):
        if key in query:
            query[key] = [str(cursor)]
            encoded = "&".join(f"{name}={values[0]}" for name, values in query.items())
            return parsed._replace(query=encoded).geturl()
    separator = "&" if parsed.query else "?"
    return f"{current}{separator}cursor={cursor}"


def item_text(item: dict[str, Any]) -> str:
    for key in ("content", "text", "body", "summary", "description", "extract"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str({key: item[key] for key in list(item.keys())[:20]})
