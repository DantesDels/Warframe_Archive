"""Multi-wiki & Wikipedia discovery provider (EN/FR, wiki.gg, official, Fandom)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, quote_plus

from ...collect.http import bot_headers
from ...slugs import slugify
from ..models import Candidate


@dataclass(frozen=True, slots=True)
class WikiProvider:
    name: str = "wiki"
    api_urls: tuple[str, ...] = ()

    def search(
        self, keywords: list[str], universe_id: str, **kwargs: Any
    ) -> list[Candidate]:
        term = " ".join(keywords[:3]).strip()
        if not term:
            return []
        client = kwargs.get("client")
        out: list[Candidate] = []
        if self.api_urls:
            for api in self.api_urls:
                out.extend(_probe_site(client, api, term, universe_id))
        else:
            out.extend(_probe_wikis(client, term, universe_id))
            out.extend(_probe_wikipedia(client, term, universe_id))
        return _unique(out)[:8]


def _probe_wikis(client: Any, term: str, uid: str) -> list[Candidate]:
    slug = slugify(term) or "wiki"
    compact = slug.replace("-", "")
    bases = (
        f"https://wiki.{compact}.com/",
        f"https://{compact}.wiki.gg/",
        f"https://{slug}.fandom.com/",
    )
    out: list[Candidate] = []
    for base in bases:
        api = f"{base.rstrip('/')}/api.php?action=query&meta=siteinfo&format=json"
        if client is None:
            out.append(_candidate(base, f"Wiki: {term}", uid, 0.62, "Wiki candidat"))
        elif _is_live_mediawiki(client, api):
            title = f"Wiki vérifié : {base}"
            out.append(_candidate(base, title, uid, 0.86, "API MediaWiki vérifiée"))
    return out


def _probe_wikipedia(client: Any, term: str, uid: str) -> list[Candidate]:
    q = quote_plus(term)
    out: list[Candidate] = []
    for lang in ("en", "fr"):
        api = (
            f"https://{lang}.wikipedia.org/w/api.php?"
            f"action=query&list=search&srsearch={q}&srlimit=2&format=json"
        )
        tag = f"Wikipédia ({lang.upper()})"
        if client is None:
            slug = quote(term.replace(" ", "_"))
            url = f"https://{lang}.wikipedia.org/wiki/{slug}"
            out.append(_candidate(url, f"{tag}: {term}", uid, 0.64, f"{tag} candidat"))
            continue
        for title in _wp_search_titles(client, api):
            slug = quote(title.replace(" ", "_"))
            url = f"https://{lang}.wikipedia.org/wiki/{slug}"
            out.append(_candidate(url, f"{tag}: {title}", uid, 0.82, f"{tag} vérifié"))
    return out


def _probe_site(client: Any, api: str, term: str, uid: str) -> list[Candidate]:
    if client is not None and _is_live_mediawiki(client, api):
        return [_candidate(api, f"Wiki/API: {term}", uid, 0.8, "API vérifiée")]
    return [_candidate(api, f"Wiki/API: {term}", uid, 0.58, "Point d'entrée wiki")]


def _json_get(client: Any, url: str) -> dict[str, Any]:
    try:
        resp = client.get(url, headers=bot_headers(), use_cache=True)
        if int(getattr(resp, "status", 0)) != 200:
            return {}
        raw = bytes(getattr(resp, "content", b"")).decode("utf-8", "replace")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _is_live_mediawiki(client: Any, api: str) -> bool:
    data = _json_get(client, api)
    return "query" in data or "batchcomplete" in data


def _wp_search_titles(client: Any, api: str) -> list[str]:
    hits = _json_get(client, api).get("query", {}).get("search", [])
    return [str(h["title"]) for h in hits if isinstance(h, dict) and h.get("title")]


def _unique(items: list[Candidate]) -> list[Candidate]:
    seen: set[str] = set()
    uniq: list[Candidate] = []
    for item in items:
        key = item.location.lower().rstrip("/")
        if key not in seen:
            seen.add(key)
            uniq.append(item)
    return uniq


def _candidate(loc: str, title: str, uid: str, score: float, proof: str) -> Candidate:
    return Candidate(
        id=f"wiki-{slugify(loc)[:28]}", universe_id=uid, kind="wiki",
        location=loc, title=title, score=score, proof=proof,
        discovered_by="wiki", score_breakdown={"authority": score, "confidence": score},
        metadata={"probe": "wiki"},
    )
