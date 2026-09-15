"""Route discovery for ``www.warframe.com/fr`` (internal-link BFS crawl).

The official site has no sitemap.xml, so the catalogue is discovered by
walking the internal links.  Only same-host absolute paths under the
configured prefix (``/fr``) are kept; assets, external hosts, fragments
and transactional segments (shop/account/support) are dropped.
"""

from __future__ import annotations

import re

_LINK_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
_SCHEME = re.compile(r"^https?://([^/]+)", re.IGNORECASE)
_ASSET = re.compile(
    r"\.(?:css|js|png|jpe?g|gif|svg|webp|ico|json|webmanifest|woff2?|pdf)$",
    re.IGNORECASE,
)


def extract_fr_paths(html: str, prefix: str, host: str) -> set[str]:
    """Normalized page paths (no scheme/host, no fragment/query, no asset).

    Only same-host absolute URLs and site-relative ``/...`` links are kept;
    fragments, queries, assets and external hosts are dropped.
    """
    paths: set[str] = set()
    for href in _LINK_RE.findall(html):
        href = href.strip()
        if not href or href.startswith(("#", "javascript:", "mailto:",
                                        "tel:", "//")):
            continue
        if href.startswith(("https://", "http://")):
            match = _SCHEME.match(href)
            if match is None or match.group(1).lower() != host:
                continue
            path = href[match.end():]
        elif href.startswith("/"):
            path = href
        else:
            continue
        path = path.split("#")[0].split("?")[0].rstrip("/") or "/"
        if path.startswith(prefix) and not _ASSET.search(path):
            paths.add(path)
    return paths


def _keep(path: str, exclude: tuple[str, ...]) -> bool:
    lowered = path.lower()
    return not any(segment in lowered for segment in exclude)


def crawl_paths(get_text, seed: str, *, prefix: str, host: str,
                exclude: tuple[str, ...], max_pages: int) -> set[str]:
    """Breadth-first walk from ``seed``; returns the reachable page paths."""
    known: set[str] = set()
    frontier = [seed]
    while frontier and len(known) < max_pages:
        path = frontier.pop(0)
        if path in known:
            continue
        known.add(path)
        html = get_text(path)
        if not html:
            continue
        for link in extract_fr_paths(html, prefix, host):
            if link not in known and _keep(link, exclude):
                frontier.append(link)
    return known


__all__ = ["crawl_paths", "extract_fr_paths"]
