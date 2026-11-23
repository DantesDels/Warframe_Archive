"""XML parser for sitemap urlset and sitemapindex documents."""

from __future__ import annotations

from xml.etree import ElementTree


def parse_sitemap_xml(body: bytes) -> tuple[list[str], list[tuple[str, str]]]:
    """Return (child_sitemap_urls, [(page_url, lastmod), ...])."""
    try:
        root = ElementTree.fromstring(body)
    except Exception:
        return [], []
    sitemaps: list[str] = []
    urls: list[tuple[str, str]] = []
    for node in root.iter():
        tag = str(node.tag).lower()
        if tag.endswith("sitemap"):
            loc = _child(node, "loc")
            if loc:
                sitemaps.append(loc)
        elif tag.endswith("url"):
            loc = _child(node, "loc")
            if loc:
                urls.append((loc, _child(node, "lastmod")))
    if not urls and not sitemaps:
        for node in root.iter():
            text = (node.text or "").strip()
            if str(node.tag).lower().endswith("loc") and text:
                urls.append((text, ""))
    return sitemaps, urls


def _child(node: ElementTree.Element, name: str) -> str:
    for child in list(node):
        if str(child.tag).lower().endswith(name):
            return (child.text or "").strip()
    return ""
