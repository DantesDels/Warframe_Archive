"""HTML extraction helpers for v1 collection."""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin, urlparse

_SKIP = r"script|style|noscript|svg|iframe|canvas|template"
_LINK_RE = re.compile(r"href=[\"']([^\"'#]+)[\"']", re.IGNORECASE)
_ASSET_RE = re.compile(
    r"\.(?:css|js|png|jpe?g|gif|svg|webp|ico|json|webmanifest|woff2?|pdf|zip|mp4|mp3)$",
    re.IGNORECASE,
)


def html_to_text(html: str) -> str:
    cleaned = re.sub(rf"(?is)<({_SKIP})[^>]*>.*?</\1>", " ", html)
    cleaned = re.sub(r"(?is)<!--.*?-->", " ", cleaned)
    cleaned = re.sub(r"(?is)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(
        r"(?is)</(p|div|li|h[1-6]|tr|section|article|main)>", "\n", cleaned
    )
    text = re.sub(r"(?is)<[^>]+>", " ", cleaned)
    text = unescape(text.replace("\xa0", " "))
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


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
