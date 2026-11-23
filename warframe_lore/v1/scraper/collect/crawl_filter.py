"""Generic URL path filtering and feed/sitemap hint extraction for HTML crawls."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

_LOCALE_SEGMENTS = frozenset({
    "en", "fr", "de", "es", "it", "pt", "ru", "ja", "ko", "zh", "pl", "nl",
})
NOISE_PATH_SEGMENTS = (
    "/login", "/signin", "/sign-in", "/signup", "/sign-up", "/register",
    "/logout", "/cart", "/checkout", "/shop", "/store", "/account",
    "/promocode", "/promo-code", "/download", "/privacy", "/terms",
    "/cookies", "/cookie", "/oauth", "/auth", "/pricing", "/billing",
    "/password", "/subscribe", "/unsubscribe",
)
_FEED_LINK_RE = re.compile(
    r'<link[^>]+rel=["\']alternate["\'][^>]+href=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def infer_path_prefix(seed_url: str, configured: str = "") -> str:
    """Return an explicit prefix or infer a 2-letter locale prefix like /en."""
    if configured.strip():
        return "/" + configured.strip().strip("/")
    path = urlparse(seed_url).path.strip("/")
    if not path:
        return ""
    first = path.split("/", 1)[0].lower()
    if first in _LOCALE_SEGMENTS and "/" not in path:
        return f"/{first}"
    return ""


def keep_crawl_url(
    url: str,
    seed_url: str,
    *,
    prefix: str = "",
    extra_excludes: tuple[str, ...] = (),
) -> bool:
    """Return True when ``url`` is within prefix and not a transactional route."""
    path = urlparse(url).path.lower().rstrip("/") or "/"
    seed_path = urlparse(seed_url).path.lower().rstrip("/") or "/"
    if prefix and not (path == prefix or path.startswith(f"{prefix}/")):
        return False
    excludes = NOISE_PATH_SEGMENTS + tuple(e.lower() for e in extra_excludes if e)
    for segment in excludes:
        if segment in path and segment not in seed_path:
            return False
    return True


def extract_alternate_feeds(html: str, base_url: str) -> list[str]:
    """Return RSS/Atom feed URLs advertised by <link rel='alternate'> tags."""
    out: list[str] = []
    for match in _FEED_LINK_RE.finditer(html):
        tag = match.group(0).lower()
        if "rss" not in tag and "atom" not in tag and "xml" not in tag:
            continue
        href = urljoin(base_url, match.group(1).strip())
        if href.startswith(("http://", "https://")) and href not in out:
            out.append(href)
    return out


def matches_topic_tags(tags: list[str] | tuple[str, ...], *texts: str) -> bool:
    """Return True when no tags are set or any tag appears in ``texts``."""
    needles = [str(t).strip().lower() for t in tags if str(t).strip()]
    if not needles:
        return True
    haystack = " ".join(str(part or "") for part in texts).lower()
    return any(needle in haystack for needle in needles)
