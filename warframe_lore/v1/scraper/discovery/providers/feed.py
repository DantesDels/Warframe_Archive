"""RSS/Atom discovery provider with optional HTTP probing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree

from ...slugs import slugify
from ..models import Candidate


@dataclass(frozen=True, slots=True)
class FeedProvider:
    client: Any | None = None
    name: str = "feed"

    def search(self, keywords: list[str], universe_id: str,
        **_: Any) -> list[Candidate]:
        out: list[Candidate] = []
        for term in keywords[:3]:
            slug = slugify(term) or "source"
            loc = f"https://{slug}.example.org/feed.xml"
            out.extend(self._probe(loc, term, universe_id, slug))
        return out

    def _probe(self, loc: str, term: str, uid: str, slug: str) -> list[Candidate]:
        if self.client is None:
            return [_candidate(uid, slug, loc, f"Flux RSS/Atom — {term}", 0.52, term)]
        try:
            resp = self.client.get(loc, use_cache=True)
            if int(getattr(resp, "status", 200)) >= 400:
                return []
            links = _links(bytes(getattr(resp, "content", b"")))
            if not links:
                return [_candidate(uid, slug, loc, f"Flux RSS/Atom — {term}", 0.6,
                    term)]
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
        tag = str(node.tag).lower()
        if tag.endswith("link"):
            href = (node.attrib.get("href") or "").strip()
            text = (node.text or "").strip()
            url = href or text
            if url.startswith("http"):
                out.append(url)
    return out


def _candidate(uid: str, slug: str, loc: str, title: str, score: float,
    term: str) -> Candidate:
    return Candidate(
        id=f"feed-{slug}", universe_id=uid, kind="website", location=loc,
        title=title, score=score,
        proof=f"Flux candidate dérivé du mot-clé « {term} »",
        discovered_by="feed", score_breakdown={"freshness": score},
        metadata={"probe": "feed"},
    )
