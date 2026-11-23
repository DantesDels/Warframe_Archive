"""HTML extraction helpers for v1 collection."""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin, urlparse

from .dom_clean import dom_to_text, has_beautifulsoup
from .html_text import html_to_text as _fallback_to_text

__all__ = ["extract_links", "html_title", "html_to_text", "markdown_to_text"]


def html_to_text(html: str) -> str:
    """Extract clean main-content text, dropping scripts, styles and chrome."""
    if has_beautifulsoup():
        text = dom_to_text(html)
        if text:
            return text
    return _fallback_to_text(html)


def markdown_to_text(html: str) -> str:
    """Extract structured Markdown when the DOM backend is available."""
    from .dom_clean import dom_to_markdown

    if has_beautifulsoup():
        text = dom_to_markdown(html)
        if text:
            return text
    return html_to_text(html)

_LINK_RE = re.compile(r"href=[\"']([^\"'#]+)[\"']", re.IGNORECASE)
_ASSET_RE = re.compile(
    r"\.(?:css|js|png|jpe?g|gif|svg|webp|ico|json|webmanifest|woff2?|pdf|zip|mp4|mp3)$",
    re.IGNORECASE,
)


def html_title(html: str) -> str:
    low = html.lower()
    start = low.find("<title")
    if start == -1:
        return ""
    start = low.find(">", start)
    end = low.find("</title>", start)
    if start == -1 or end == -1 or end <= start:
        return ""
    return unescape(" ".join(html[start + 1 : end].split()))[:180]


def extract_links(html: str, base_url: str, *, same_host: bool = True) -> list[str]:
    base = urlparse(base_url)
    found: list[str] = []
    seen: set[str] = set()
    for href in _LINK_RE.findall(html):
        href = href.strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "data:")):
            continue
        if any(tok in href.lower() for tok in ("{", "}", "%7b", "%7d")):
            continue
        abs_url = urljoin(base_url, href).split("#")[0]
        parsed = urlparse(abs_url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if same_host and parsed.netloc != base.netloc:
            continue
        if _ASSET_RE.search(parsed.path):
            continue
        norm = abs_url.rstrip("/")
        if norm and norm not in seen:
            seen.add(norm)
            found.append(norm)
    return found
