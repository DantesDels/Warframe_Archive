"""Wiki/API directory discovery provider."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

from ...slugs import slugify
from ..models import Candidate


@dataclass(frozen=True, slots=True)
class WikiProvider:
    name: str = "wiki"
    api_urls: tuple[str, ...] = ()

    def search(
        self, keywords: list[str], universe_id: str, **kwargs: Any
    ) -> list[Candidate]:
        term = " ".join(keywords[:2]).strip()
        if not term:
            return []
        client = kwargs.get("client")
        out: list[Candidate] = []
        apis = list(self.api_urls) or _wiki_apis(term)
        for api in apis:
            if client is not None:
                try:
                    resp = client.get(
                        api,
                        headers={"Accept": "application/json"},
                        use_cache=True,
                    )
                    if int(getattr(resp, "status", 0)) == 200:
                        body = bytes(getattr(resp, "content", b""))
                        if _looks_like_mediawiki(body):
                            out.append(
                                _candidate(
                                    api, term, universe_id, 0.72,
                                    "MediaWiki API vérifiée",
                                )
                            )
                            continue
                except Exception:
                    pass
            out.append(
                _candidate(
                    api, term, universe_id, 0.58, "Point d'entrée wiki/API candidat"
                )
            )
        # dedupe by location
        seen: set[str] = set()
        uniq: list[Candidate] = []
        for c in out:
            k = c.location.lower().rstrip("/")
            if k not in seen:
                seen.add(k)
                uniq.append(c)
        return uniq[:4]


def _wiki_apis(term: str) -> list[str]:
    slug = slugify(term) or "wiki"
    q = quote_plus(term.replace(" ", "_"))
    return [
        f"https://{slug}.fandom.com/api.php?action=query&meta=siteinfo&format=json",
        f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&format=json",
    ]


def _looks_like_mediawiki(body: bytes) -> bool:
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except Exception:
        return False
    return isinstance(data, dict) and ("query" in data or "batchcomplete" in data)


def _candidate(api: str, term: str, uid: str, score: float, proof: str) -> Candidate:
    return Candidate(
        id=f"wiki-{slugify(api)[:28]}",
        universe_id=uid,
        kind="wiki",
        location=api,
        title=f"Wiki/API: {term}",
        score=score,
        proof=proof,
        discovered_by="wiki",
        score_breakdown={"authority": score, "confidence": score},
        metadata={"probe": "wiki", "query": term},
    )
