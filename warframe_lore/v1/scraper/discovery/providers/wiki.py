"""Wiki/API directory discovery provider."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...slugs import slugify
from ..models import Candidate


@dataclass(frozen=True, slots=True)
class WikiProvider:
    name: str = "wiki"

    def search(self, keywords: list[str], universe_id: str,
        **_: Any) -> list[Candidate]:
        out: list[Candidate] = []
        for term in keywords[:2]:
            slug = slugify(term) or "wiki"
            loc = f"https://{slug}.fandom.com/api.php"
            out.append(
                Candidate(
                    id=f"wiki-{slug}",
                    universe_id=universe_id,
                    kind="wiki",
                    location=loc,
                    title=f"Wiki/API — {term}",
                    score=0.58,
                    proof=f"Point d'entrée wiki/API candidat pour « {term} »",
                    discovered_by="wiki",
                    score_breakdown={"authority": 0.58},
                    metadata={"probe": "wiki"},
                )
            )
        return out
