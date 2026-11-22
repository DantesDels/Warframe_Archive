"""Manifest/index expansion helpers for generic collection."""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin

_URL_RE = re.compile(r"https?://[^\s\"'<>]+")
_REL_RE = re.compile(r"(?:^|\s)(/[A-Za-z0-9_./\-]+)")


def extract_manifest_urls(text: str, base_url: str, *, limit: int = 50) -> list[str]:
    """Extract likely child resource URLs from index/manifest text."""
    candidates: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for url in _from_json(line, base_url):
            _add(candidates, seen, url, limit)
        for match in _URL_RE.findall(line):
            _add(candidates, seen, match.rstrip("),."), limit)
        for match in _REL_RE.findall(line):
            _add(candidates, seen, urljoin(base_url, match.strip()), limit)
        if len(candidates) >= limit:
            break
    return candidates[:limit]


def _from_json(line: str, base_url: str) -> list[str]:
    if not (line.startswith("{") or line.startswith("[")):
        return []
    try:
        payload = json.loads(line)
    except Exception:
        return []
    out: list[str] = []

    def walk(value):
        if isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, str) and k.lower() in {"url", "href", "path", "file"}:
                    out.append(urljoin(base_url, v))
                else:
                    walk(v)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return out


def _add(out: list[str], seen: set[str], url: str, limit: int) -> None:
    if len(out) >= limit:
        return
    norm = url.strip().rstrip("/")
    if not norm or norm in seen:
        return
    if norm.startswith("http://") or norm.startswith("https://"):
        seen.add(norm)
        out.append(norm)
