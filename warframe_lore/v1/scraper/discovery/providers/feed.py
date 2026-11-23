"""RSS/Atom discovery provider probing real universe hosts and HTML links."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

from ...collect.crawl_filter import extract_alternate_feeds
from ...slugs import slugify
from ..models import Candidate

_FEED_PATHS = ("/feed", "/feed.xml", "/rss.xml", "/atom.xml")


@dataclass(frozen=True, slots=True)
class FeedProvider:
    client: Any | None = None
    name: str = "feed"

    def search(
        self, keywords: list[str], universe_id: str, **kwargs: Any
    ) -> list[Candidate]:
        client = self.client or kwargs.get("client")
        sources = _source_urls(kwargs.get("universe"))
        out: list[Candidate] = []
        if sources:
            for src in sources[:5]:
                out.extend(_probe_source(client, src, keywords, universe_id))
            if out:
                return out
        for term in keywords[:3]:
            slug = slugify(term) or "source"
            loc = f"https://{slug}.example.org/feed.xml"
            out.extend(_probe_feed(client, loc, term, universe_id, slug))
        return out


def _source_urls(universe: Any) -> list[str]:
    if not isinstance(universe, dict):
        return []
    cfg = universe.get("_discovery_cfg") or {}
    existing = list(cfg.get("existing_sources") or [])
    seeds = list(cfg.get("discovery_seeds") or [])
    return [str(u) for u in existing + seeds if str(u).startswith(("http://", "https://"))]


def _probe_source(
    client: Any, src_url: str, keywords: list[str], uid: str
) -> list[Candidate]:
    parsed = urlparse(src_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    term = " ".join(keywords[:2]).strip() or parsed.netloc
    slug = slugify(parsed.netloc) or "feed"
    targets = _html_feeds(client, src_url) + [f"{base}{p}" for p in _FEED_PATHS]
    seen: set[str] = set()
    for target in targets:
        if target in seen:
            continue
        seen.add(target)
        found = _probe_feed(client, target, term, uid, slug, emit_feed=True)
        if found:
            return found
    return []


def _html_feeds(client: Any, url: str) -> list[str]:
    if client is None:
        return []
    try:
        resp = client.get(url, use_cache=True)
        if int(getattr(resp, "status", 200)) >= 400:
            return []
        html = bytes(getattr(resp, "content", b"")).decode("utf-8", errors="replace")
        return extract_alternate_feeds(html, url)
    except Exception:
        return []


def _probe_feed(
    client: Any, loc: str, term: str, uid: str, slug: str, *, emit_feed: bool = False
) -> list[Candidate]:
    if client is None:
        return [_candidate(uid, slug, loc, f"Flux RSS/Atom — {term}", 0.52, term)]
    try:
        resp = client.get(loc, use_cache=True)
        if int(getattr(resp, "status", 200)) >= 400:
            return []
        links = _links(bytes(getattr(resp, "content", b"")))
        if emit_feed and links:
            return [_candidate(uid, slug, loc, f"Flux RSS/Atom — {term}", 0.76, term)]
        if not links:
            return [_candidate(uid, slug, loc, f"Flux RSS/Atom — {term}", 0.6, term)]
        return [
            _candidate(uid, f"{slug}-{i}", url, f"Flux: {term}", 0.7, term)
            for i, url in enumerate(links[:10])
        ]
    except Exception:
        return []


def _links(body: bytes) -> list[str]:
    try:
        root = ElementTree.fromstring(body)
    except Exception:
        return []
    out: list[str] = []
    for node in root.iter():
        if str(node.tag).lower().endswith("link"):
            url = (node.attrib.get("href") or node.text or "").strip()
            if url.startswith("http"):
                out.append(url)
    return out


def _candidate(
    uid: str, slug: str, loc: str, title: str, score: float, term: str
) -> Candidate:
    return Candidate(
        id=f"feed-{slug}", universe_id=uid, kind="website", location=loc,
        title=title, score=score,
        proof=f"Flux RSS/Atom découvert pour « {term} »",
        discovered_by="feed", score_breakdown={"freshness": score},
        metadata={"probe": "feed"},
    )
