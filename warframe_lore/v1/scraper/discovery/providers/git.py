"""Git repository discovery provider (opt-in)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...slugs import slugify
from ..models import Candidate


@dataclass(frozen=True, slots=True)
class GitProvider:
    name: str = "git"

    def search(self, keywords: list[str], universe_id: str,
        **_: Any) -> list[Candidate]:
        out: list[Candidate] = []
        for term in keywords[:2]:
            slug = slugify(term) or "repo"
            loc = f"https://github.com/search?q={slug}&type=repositories"
            out.append(
                Candidate(
                    id=f"git-{slug}",
                    universe_id=universe_id,
                    kind="website",
                    location=loc,
                    title=f"Dépôt Git — {term}",
                    score=0.5,
                    proof=f"Recherche de dépôt Git pour « {term} »",
                    discovered_by="git",
                    score_breakdown={"authority": 0.5},
                    metadata={"probe": "git"},
                )
            )
        return out
