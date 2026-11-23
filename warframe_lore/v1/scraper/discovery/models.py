"""Candidate source model produced by discovery providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

CANDIDATE_STATUSES = ("proposed", "active", "suspended", "blacklisted")
DISCOVERY_PROVIDERS = ("keywords", "web_search", "sitemap", "feed", "git", "wiki",
    "api")


@dataclass(frozen=True, slots=True)
class Candidate:
    """A source proposition awaiting user curation."""

    id: str
    universe_id: str
    kind: str
    location: str
    title: str
    score: float
    proof: str
    discovered_by: str = "keywords"
    status: str = "proposed"
    force_update: bool = False
    score_breakdown: dict[str, float] = field(
        default_factory=lambda: cast(dict[str, float], {})
    )
    metadata: dict[str, Any] = field(
        default_factory=lambda: cast(dict[str, Any], {})
    )

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 1:
            raise ValueError("candidate score must be between 0 and 1")
        if self.status not in CANDIDATE_STATUSES:
            raise ValueError(f"unknown candidate status: {self.status}")
