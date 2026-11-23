"""Sitemap connector with lastmod delta support."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree

from ....ports.outbound.sources import CollectedPage, ConnectorContext


class SitemapConnector:
    name = "sitemap"
    kinds = ("sitemap", "website")

    def can_handle(self, source: dict[str, Any], _ctx: ConnectorContext) -> bool:
        loc = str(source.get("location", "")).lower()
        kind = str(source.get("kind", "")).lower()
        return (
            kind == "sitemap"
            or loc.endswith("sitemap.xml")
            or "sitemap" in loc
        )

    def collect(self, source: dict[str, Any],
        ctx: ConnectorContext) -> list[CollectedPage]:
        url = str(source.get("location", "")).strip()
        resp = ctx.client.get(
            url, use_cache=bool(ctx.limits.get("use_cache", True))
        )
        body = bytes(getattr(resp, "content", b""))
        entries = _parse(body)
        state = cast_state(ctx, url)
        pages: list[CollectedPage] = []
        max_pages = int(ctx.limits.get("max_pages_per_source", 25))
        for loc, lastmod in entries[:max_pages]:
            prev = str(state.get(loc, ""))
            incremental = bool(ctx.limits.get("incremental", True))
            if lastmod and prev == lastmod and incremental:
                continue
            pages.append(
                CollectedPage(
                    title=loc.rsplit("/", 1)[-1] or loc,
                    url=loc,
                    content=f"Source sitemap: {url}\nlastmod: {lastmod}",
                    metadata={"lastmod": lastmod, "sitemap": url},
                )
            )
            if lastmod:
                state[loc] = lastmod
        return pages


def _parse(body: bytes) -> list[tuple[str, str]]:
    try:
        root = ElementTree.fromstring(body)
    except Exception:
        return []
    out: list[tuple[str, str]] = []
    for node in root.iter():
        if not str(node.tag).lower().endswith("url"):
            continue
        loc = _child(node, "loc")
        if loc:
            out.append((loc, _child(node, "lastmod")))
    if not out:
        for node in root.iter():
            if str(node.tag).lower().endswith("loc") and (node.text or "").strip():
                out.append((node.text.strip(), ""))
    return out


def _child(node: ElementTree.Element, name: str) -> str:
    for c in list(node):
        if str(c.tag).lower().endswith(name):
            return (c.text or "").strip()
    return ""


def cast_state(ctx: ConnectorContext, url: str) -> dict[str, str]:
    root = ctx.limits.setdefault("connector_state", {})
    sm = root.setdefault("sitemaps", {})
    bucket = sm.setdefault(url, {})
    return bucket  # type: ignore[return-value]
