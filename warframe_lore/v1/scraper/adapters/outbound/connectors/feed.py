"""RSS/Atom connector."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree

from ....ports.outbound.sources import CollectedPage, ConnectorContext


class FeedConnector:
    name = "feed"
    kinds = ("feed", "rss", "atom", "website")

    def can_handle(self, source: dict[str, Any], _ctx: ConnectorContext) -> bool:
        loc = str(source.get("location", "")).lower()
        kind = str(source.get("kind", "")).lower()
        return kind in {"feed", "rss", "atom"} or (
            loc.endswith((".rss", ".atom", ".xml")) and "feed" in loc
        )

    def collect(self, source: dict[str, Any],
        ctx: ConnectorContext) -> list[CollectedPage]:
        url = str(source.get("location", "")).strip()
        resp = ctx.client.get(
            url, use_cache=bool(ctx.limits.get("use_cache", True))
        )
        entries = _parse(bytes(getattr(resp, "content", b"")))
        state = _feed_state(ctx, url)
        pages: list[CollectedPage] = []
        incremental = bool(ctx.limits.get("incremental", True))
        for item in entries[: int(ctx.limits.get("max_pages_per_source", 25))]:
            link = item.get("link") or url
            title = item.get("title") or link
            stamp = str(item.get("updated") or item.get("published") or "")
            prev = str(state.get(link, ""))
            if incremental and stamp and prev == stamp:
                continue
            content = "\n".join([item.get("summary", ""), stamp]).strip()
            pages.append(
                CollectedPage(
                    title=title,
                    url=link,
                    content=content or title,
                    metadata=item,
                )
            )
            if stamp:
                state[link] = stamp
        return pages


def _feed_state(ctx: ConnectorContext, url: str) -> dict[str, str]:
    root = ctx.limits.setdefault("connector_state", {})
    feeds = root.setdefault("feeds", {})
    bucket = feeds.setdefault(url, {})
    return bucket  # type: ignore[return-value]


def _parse(body: bytes) -> list[dict[str, str]]:
    try:
        root = ElementTree.fromstring(body)
    except Exception:
        return []
    out: list[dict[str, str]] = []
    for node in root.iter():
        tag = str(node.tag).lower()
        if tag.endswith("entry") or tag.endswith("item"):
            out.append(_entry(node))
    return out


def _entry(node: ElementTree.Element) -> dict[str, str]:
    item: dict[str, str] = {}
    for c in list(node):
        tag = str(c.tag).lower()
        if tag.endswith("link"):
            item["link"] = (c.attrib.get("href") or c.text or "").strip()
        elif tag.endswith(
            ("title", "summary", "description", "updated", "published", "id")
        ):
            key = tag.rsplit("}", 1)[-1]
            item[key] = (c.text or "").strip()
    if "description" in item and "summary" not in item:
        item["summary"] = item["description"]
    return item
