"""Sitemap discovery provider probing real universe hosts and robots.txt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from ...collect.sitemap_xml import parse_sitemap_xml
from ...slugs import slugify
from ..models import Candidate


@dataclass(frozen=True, slots=True)
class SitemapProvider:
    client: Any | None = None
    name: str = "sitemap"

    def search(
        self, keywords: list[str], universe_id: str, **kwargs: Any
    ) -> list[Candidate]:
        client = self.client or kwargs.get("client")
        hosts = _source_hosts(kwargs.get("universe"))
        out: list[Candidate] = []
        if hosts:
            for base in hosts[:5]:
                out.extend(_probe_host(client, base, keywords, universe_id))
            if out:
                return out
        for term in keywords[:3]:
            slug = slugify(term) or "source"
            loc = f"https://{slug}.example.org/sitemap.xml"
            out.extend(_probe_sitemap(client, loc, term, universe_id, slug))
        return out


def _source_hosts(universe: Any) -> list[str]:
    if not isinstance(universe, dict):
        return []
    cfg = universe.get("_discovery_cfg") or {}
    existing = list(cfg.get("existing_sources") or [])
    seeds = list(cfg.get("discovery_seeds") or [])
    hosts: list[str] = []
    for url in existing + seeds:
        parsed = urlparse(str(url))
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            base = f"{parsed.scheme}://{parsed.netloc}"
            if base not in hosts:
                hosts.append(base)
    return hosts


def _probe_host(
    client: Any, base: str, keywords: list[str], uid: str
) -> list[Candidate]:
    term = " ".join(keywords[:2]).strip() or urlparse(base).netloc
    slug = slugify(urlparse(base).netloc) or "site"
    targets = _robots_sitemaps(client, base) + [
        f"{base}/sitemap.xml", f"{base}/sitemap_index.xml",
    ]
    seen: set[str] = set()
    for target in targets:
        if target in seen:
            continue
        seen.add(target)
        found = _probe_sitemap(client, target, term, uid, slug, emit_sitemap=True)
        if found:
            return found
    return []


def _robots_sitemaps(client: Any, base: str) -> list[str]:
    if client is None:
        return []
    try:
        resp = client.get(f"{base}/robots.txt", use_cache=True)
        if int(getattr(resp, "status", 200)) >= 400:
            return []
        text = bytes(getattr(resp, "content", b"")).decode("utf-8", errors="replace")
    except Exception:
        return []
    return [
        line.split(":", 1)[1].strip()
        for line in text.splitlines()
        if line.lower().startswith("sitemap:") and ":" in line
    ]


def _probe_sitemap(
    client: Any, loc: str, term: str, uid: str, slug: str, *, emit_sitemap: bool = False
) -> list[Candidate]:
    if client is None:
        return [_candidate(uid, slug, loc, f"Sitemap — {term}", 0.55, term)]
    try:
        resp = client.get(loc, use_cache=True)
        if int(getattr(resp, "status", 200)) >= 400:
            return []
        body = bytes(getattr(resp, "content", b""))
        sitemaps, urls = parse_sitemap_xml(body)
        if emit_sitemap and (sitemaps or urls):
            count = len(urls) or len(sitemaps)
            title = f"Sitemap ({count} entrées)"
            return [_candidate(uid, slug, loc, title, 0.78, term, kind="sitemap")]
        if not urls:
            return [_candidate(uid, slug, loc, f"Sitemap — {term}", 0.62, term)]
        return [
            _candidate(uid, f"{slug}-{i}", u, f"Sitemap: {term}", 0.72, term)
            for i, (u, _) in enumerate(urls[:10])
        ]
    except Exception:
        return []


def _candidate(
    uid: str, slug: str, loc: str, title: str, score: float, term: str,
    *, kind: str = "website",
) -> Candidate:
    return Candidate(
        id=f"sitemap-{slug}", universe_id=uid, kind=kind, location=loc,
        title=title, score=score,
        proof=f"Sitemap découvert pour « {term} »",
        discovered_by="sitemap", score_breakdown={"authority": score},
        metadata={"probe": "sitemap"},
    )
