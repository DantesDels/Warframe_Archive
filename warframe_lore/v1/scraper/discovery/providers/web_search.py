"""Web search discovery provider (opt-in, configurable endpoint)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...slugs import slugify
from ..models import Candidate


@dataclass(frozen=True, slots=True)
class WebSearchProvider:
    """Config-driven web search hook; no hardcoded external API key."""

    endpoint: str = ""
    name: str = "web_search"

    def search(self, keywords: list[str], universe_id: str,
        **_: Any) -> list[Candidate]:
        if not self.endpoint.strip():
            return []
        out: list[Candidate] = []
        term = " ".join(keywords[:3]).strip() or "source"
        slug = slugify(term) or "source"
        url = self.endpoint.replace("{query}", slug).replace("{q}", slug)
        out.append(
            Candidate(
                id=f"web-{slug}",
                universe_id=universe_id,
                kind="website",
                location=url,
                title=f"Recherche web — {term}",
                score=0.6,
                proof="Recherche web configurée (endpoint utilisateur)",
                discovered_by="web_search",
                score_breakdown={"authority": 0.5, "confidence": 0.6},
                metadata={"probe": "web_search", "endpoint": self.endpoint},
            )
        )
        return out
