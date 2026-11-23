"""Watcher classification and fingerprinting for RSS, sitemaps, GitHub and APIs."""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlparse

from .parsers import (
    hash_items,
    parse_feed_items,
    parse_github_releases,
    parse_json_snapshot,
    parse_sitemap_items,
)

_GITHUB_REPO_RE = re.compile(r"^/([^/]+)/([^/]+?)(?:\.git)?/?$")
_CHANGELOG_HINTS = (
    "changelog", "patch-notes", "patchnotes", "release-notes",
    "releases", "announcements", "news", "updates",
)
_FEED_HINTS = ("/rss", "/feed", "/atom", ".rss", ".atom", "feed.xml", "rss.xml")
_PARSERS = {
    "github_release": parse_github_releases,
    "rss": parse_feed_items,
    "sitemap": parse_sitemap_items,
    "api": parse_json_snapshot,
}


def infer_watcher_kind(source: dict[str, Any]) -> str:
    """Classify a source into github_release, rss, sitemap, changelog or api."""
    kind = str(source.get("kind", "")).strip().lower()
    url = str(source.get("location", "")).strip()
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if host in {"github.com", "www.github.com", "api.github.com"}:
        if "/releases" in path or _GITHUB_REPO_RE.match(parsed.path):
            return "github_release"
    if kind == "feed" or any(h in path for h in _FEED_HINTS):
        return "rss"
    if kind == "sitemap" or ("sitemap" in path and path.endswith(".xml")):
        return "sitemap"
    if any(h in path for h in _CHANGELOG_HINTS):
        return "changelog"
    return "api" if kind == "api" else "changelog"


def watch_url_for(source: dict[str, Any], watcher_kind: str) -> str:
    """Resolve the best conditional-poll endpoint for a source."""
    url = str(source.get("location", "")).strip()
    if watcher_kind == "github_release":
        parsed = urlparse(url)
        if parsed.netloc.lower() in {"github.com", "www.github.com"}:
            match = _GITHUB_REPO_RE.match(parsed.path)
            if match:
                owner, repo = match.group(1), match.group(2)
                return f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=5"
    return url


def extract_change_fingerprint(
    watcher_kind: str, body: bytes
) -> tuple[str, list[str]]:
    """Return (sha256_fingerprint, top_items) for structured or raw watch bodies."""
    parser = _PARSERS.get(watcher_kind)
    if parser is not None:
        items = parser(body)
        if items:
            return hash_items(items), items[:5]
    normalized = " ".join(body.decode("utf-8", errors="replace").split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return digest, ([normalized[:80]] if normalized else [])
