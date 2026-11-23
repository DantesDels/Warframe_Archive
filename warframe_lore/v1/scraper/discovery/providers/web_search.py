"""Web search discovery provider (opt-in, configurable endpoint)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

from ...slugs import slugify
from ..models import Candidate


@dataclass(frozen=True, slots=True)
class WebSearchProvider:
    """Config-driven web search hook; no hardcoded external API key."""

    endpoint: str = ""
    headers: dict[str, str] | None = None
    name: str = "web_search"

    def search(
        self, keywords: list[str], universe_id: str, **kwargs: Any
    ) -> list[Candidate]:
        if not self.endpoint.strip():
            return []
        term = " ".join(keywords[:4]).strip() or "source"
        slug = slugify(term) or "source"
        q = quote_plus(term)
        url = self.endpoint.replace("{query}", slug).replace("{q}", q)
        client = kwargs.get("client")
        headers = dict(self.headers or {})
        headers.update(kwargs.get("headers") or {})
        if client is not None:
            try:
                resp = client.get(url, headers=headers, use_cache=True)
                body = bytes(getattr(resp, "content", b""))
                parsed = _parse_results(body, term, universe_id)
                if parsed:
                    return parsed
            except Exception:
                pass
        return [
            Candidate(
                id=f"web-{slug}",
                universe_id=universe_id,
                kind="website",
                location=url,
                title=f"Recherche web: {term}",
                score=0.55,
                proof="Endpoint web search configuré (probe générique)",
                discovered_by="web_search",
                score_breakdown={"authority": 0.5, "confidence": 0.55},
                metadata={"probe": "web_search", "endpoint": self.endpoint},
            )
        ]


def _parse_results(body: bytes, term: str, uid: str) -> list[Candidate]:
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except Exception:
        return []
    items = []
    if isinstance(data, dict):
        for key in ("results", "items", "data", "webPages", "value"):
            val = data.get(key)
            if isinstance(val, dict) and "value" in val:
                val = val.get("value")
            if isinstance(val, list):
                items = val
                break
    if not isinstance(items, list):
        return []
    out: list[Candidate] = []
    for i, item in enumerate(items[:10]):
        if not isinstance(item, dict):
            continue
        link = str(
            item.get("url") or item.get("link") or item.get("href") or ""
        ).strip()
        title = str(item.get("title") or item.get("name") or link).strip()
        snippet = str(item.get("snippet") or item.get("description") or "").strip()
        if not link.startswith("http"):
            continue
        out.append(
            Candidate(
                id=f"web-{slugify(title)[:24] or i}",
                universe_id=uid,
                kind="website",
                location=link,
                title=title[:180] or link,
                score=0.68,
                proof=snippet[:180] or f"Résultat web search pour {term}",
                discovered_by="web_search",
                score_breakdown={"authority": 0.55, "confidence": 0.7},
                metadata={"probe": "web_search", "query": term},
            )
        )
    return out
