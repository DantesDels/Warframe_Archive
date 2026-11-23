"""Sitemap discovery provider with optional HTTP probing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree

from ...slugs import slugify
from ..models import Candidate


@dataclass(frozen=True, slots=True)
class SitemapProvider:
    client: Any | None = None
    name: str = "sitemap"

    def search(self, keywords: list[str], universe_id: str,
        **_: Any) -> list[Candidate]:
        out: list[Candidate] = []
        for term in keywords[:3]:
            slug = slugify(term) or "source"
            loc = f"https://{slug}.example.org/sitemap.xml"
            out.extend(self._probe(loc, term, universe_id, slug))
        return out

    def _probe(self, loc: str, term: str, uid: str, slug: str) -> list[Candidate]:
        if self.client is None:
            return [_candidate(uid, slug, loc, f"Sitemap — {term}", 0.55, term)]
        try:
            resp = self.client.get(loc, use_cache=True)
            if int(getattr(resp, "status", 200)) >= 400:
                return []
            body = bytes(getattr(resp, "content", b""))
            urls = _urls_from_sitemap(body)
            if not urls:
                return [_candidate(uid, slug, loc, f"Sitemap — {term}", 0.62, term)]
            return [
                _candidate(uid, f"{slug}-{i}", url, f"Sitemap: {term}", 0.72, term)
                for i, url in enumerate(urls[:10])
            ]
        except Exception:
            return []


def _urls_from_sitemap(body: bytes) -> list[str]:
    try:
        root = ElementTree.fromstring(body)
    except Exception:
        return []
    urls: list[str] = []
    for loc in root.iter():
        if str(loc.tag).lower().endswith("loc") and (loc.text or "").strip():
            urls.append(loc.text.strip())
    return urls


def _candidate(uid: str, slug: str, loc: str, title: str, score: float,
    term: str) -> Candidate:
    return Candidate(
        id=f"sitemap-{slug}", universe_id=uid, kind="website", location=loc,
        title=title, score=score,
        proof=f"Sitemap candidate dérivé du mot-clé « {term} »",
        discovered_by="sitemap", score_breakdown={"authority": score},
        metadata={"probe": "sitemap"},
    )
