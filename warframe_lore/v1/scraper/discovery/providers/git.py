"""Git repository discovery provider (opt-in)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

from ...slugs import slugify
from ..models import Candidate


@dataclass(frozen=True, slots=True)
class GitProvider:
    name: str = "git"
    api_base: str = "https://api.github.com/search/repositories"

    def search(
        self, keywords: list[str], universe_id: str, **kwargs: Any
    ) -> list[Candidate]:
        term = " ".join(keywords[:3]).strip()
        if not term:
            return []
        client = kwargs.get("client")
        if client is not None:
            try:
                url = f"{self.api_base}?q={quote_plus(term)}&per_page=5"
                resp = client.get(
                    url,
                    headers={"Accept": "application/vnd.github+json"},
                    use_cache=True,
                )
                body = bytes(getattr(resp, "content", b""))
                parsed = _parse(body, universe_id, term)
                if parsed:
                    return parsed
            except Exception:
                pass
        slug = slugify(term) or "repo"
        loc = f"https://github.com/search?q={quote_plus(term)}&type=repositories"
        return [
            Candidate(
                id=f"git-{slug}",
                universe_id=universe_id,
                kind="website",
                location=loc,
                title=f"D?p?ts Git: {term}",
                score=0.5,
                proof=f"Recherche de d?p?t Git pour '{term}'",
                discovered_by="git",
                score_breakdown={"authority": 0.5, "confidence": 0.45},
                metadata={"probe": "git", "query": term},
            )
        ]


def _parse(body: bytes, uid: str, term: str) -> list[Candidate]:
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except Exception:
        return []
    items = data.get("items", []) if isinstance(data, dict) else []
    out: list[Candidate] = []
    for i, item in enumerate(items[:5]):
        if not isinstance(item, dict):
            continue
        link = str(item.get("html_url") or "").strip()
        if not link.startswith("http"):
            continue
        name = str(item.get("full_name") or item.get("name") or link)
        desc = str(item.get("description") or "").strip()
        stars = item.get("stargazers_count", 0)
        out.append(
            Candidate(
                id=f"git-{slugify(name)[:24] or i}",
                universe_id=uid,
                kind="website",
                location=link,
                title=name[:180],
                score=0.65,
                proof=(desc[:140] or f"D?p?t Git pour {term}") + f" (?{stars})",
                discovered_by="git",
                score_breakdown={"authority": 0.7, "confidence": 0.75},
                metadata={"probe": "git", "stars": stars, "query": term},
            )
        )
    return out
