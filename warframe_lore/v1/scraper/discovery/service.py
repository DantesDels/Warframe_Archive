"""Discovery orchestration: threshold filtering and deduplication."""

from __future__ import annotations

from typing import Any

from .models import Candidate
from .providers import KeywordProvider


def keywords_for(name: str, description: str = "") -> list[str]:
    """Extract meaningful keywords from a Universe label and description."""
    words = [
        word.strip(" ,.;:!?()[]")
        for word in f"{name} {description}".split()
    ]
    return list(dict.fromkeys(word for word in words if len(word) >= 3))[:6]


def discover(
    universe: dict[str, Any],
    min_relevance: int,
    provider: KeywordProvider | None = None,
) -> list[Candidate]:
    """Return deduplicated candidates scoring at least ``min_relevance``%."""
    active_provider = provider or KeywordProvider()
    keywords = keywords_for(universe["name"], universe.get("description", ""))
    found = active_provider.search(keywords, universe["id"])
    kept = [item for item in found if item.score * 100 >= min_relevance]
    unique = list({item.location: item for item in kept}.values())
    return sorted(unique, key=lambda item: item.score, reverse=True)
