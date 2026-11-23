"""Structured payload parsers for RSS/Atom, sitemaps, GitHub releases and APIs."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET


def hash_items(items: list[str]) -> str:
    """Return a deterministic SHA-256 hex digest for a list of item keys."""
    return hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()


def parse_github_releases(body: bytes) -> list[str]:
    """Extract release tags and dates from a GitHub Releases API payload."""
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    entries = (
        data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
    )
    out: list[str] = []
    for item in entries[:10]:
        if isinstance(item, dict):
            tag = str(item.get("tag_name") or item.get("name") or item.get("id") or "")
            pub = str(item.get("published_at") or item.get("created_at") or "")
            if tag:
                out.append(f"{tag} ({pub[:10]})" if pub else tag)
    return out


def parse_feed_items(body: bytes) -> list[str]:
    """Extract titles and timestamps from RSS or Atom XML payloads."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    items: list[str] = []
    for elem in root.iter():
        if elem.tag.rsplit("}", 1)[-1].lower() not in {"item", "entry"}:
            continue
        title = _child_text(elem, {"title"}) or _child_text(elem, {"id", "link"})
        stamp = _child_text(elem, {"updated", "pubdate", "published"})
        if title:
            items.append(f"{title} [{stamp}]" if stamp else title)
        if len(items) >= 20:
            break
    return items


def parse_sitemap_items(body: bytes) -> list[str]:
    """Extract URL and lastmod markers from XML sitemap payloads."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    items: list[str] = []
    for elem in root.iter():
        if elem.tag.rsplit("}", 1)[-1].lower() not in {"url", "sitemap"}:
            continue
        loc = _child_text(elem, {"loc"})
        lastmod = _child_text(elem, {"lastmod"})
        if loc:
            items.append(f"{loc}@{lastmod}" if lastmod else loc)
        if len(items) >= 100:
            break
    return items


def parse_json_snapshot(body: bytes) -> list[str]:
    """Canonicalize a JSON API response for stable change detection."""
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return [canonical[:2000]] if canonical else []


def _child_text(elem: ET.Element, names: set[str]) -> str:
    for child in elem:
        if child.tag.rsplit("}", 1)[-1].lower() in names and child.text:
            return child.text.strip()
    return ""
