"""Cache helpers for outbound HTTP adapter."""

from __future__ import annotations

from typing import Any


def cache_key(url: str, params: dict[str, Any] | None, headers: dict[str, str]) -> str:
    return (f"{url}|{sorted((params or {}).items())}|"
            f"{headers.get('User-Agent','')}|{headers.get('Accept','')}")


def conditional_headers(
    headers: dict[str, str], cached: dict[str, Any] | None
) -> dict[str, str]:
    req = dict(headers)
    if not cached:
        return req
    if cached.get("etag"):
        req["If-None-Match"] = cached["etag"]
    if cached.get("last_modified"):
        req["If-Modified-Since"] = cached["last_modified"]
    return req


def store(cache: Any, key: str, resp: Any) -> None:
    if cache is None or resp.status != 200:
        return
    cache.set_content(key, resp.content)
    cache.set(key, {
        "url": resp.url, "etag": resp.headers.get("ETag"),
        "last_modified": resp.headers.get("Last-Modified"),
        "content_type": resp.content_type,
        "headers": resp.headers, "encoding": resp.encoding,
    })
