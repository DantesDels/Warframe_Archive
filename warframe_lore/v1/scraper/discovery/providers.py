"""Deterministic, offline keyword discovery provider."""

from __future__ import annotations

from dataclasses import dataclass

from ..slugs import slugify
from .models import Candidate

SOURCE_TEMPLATES = (
    ("Encyclopédie", "website", "https://{lang}.wikipedia.org/wiki/{term}", 0.86),
    ("Documentation", "website", "https://{term}.example.org/docs", 0.74),
    ("API publique", "api", "https://api.example.org/v1/{term}", 0.68),
    ("Document PDF", "document", "documents/{term}.pdf", 0.61),
)


def adjusted_score(base_score: float, term: str, index: int) -> float:
    """Derive a stable score variation so discovery is reproducible."""
    variance = (sum(term.encode("utf-8")) + index * 7) % 12 - 6
    return round(min(0.99, max(0.05, base_score + variance / 100)), 2)


@dataclass(frozen=True, slots=True)
class KeywordProvider:
    """Build generic candidates from keywords without any domain hardcoding."""

    language: str = "fr"

    def search(self, keywords: list[str], universe_id: str) -> list[Candidate]:
        candidates: list[Candidate] = []
        for keyword in keywords:
            term = keyword.strip()
            if not term:
                continue
            slug = slugify(term) or "source"
            for index, (title, kind, template, base_score) in enumerate(
                SOURCE_TEMPLATES,
            ):
                candidates.append(
                    Candidate(
                        id=f"{slug}-{index}",
                        universe_id=universe_id,
                        kind=kind,
                        location=template.format(lang=self.language, term=slug),
                        title=f"{title} — {term}",
                        score=adjusted_score(base_score, term, index),
                        proof=f"Mot-clé « {term} » issu du nom de l'Univers",
                    ),
                )
        return candidates
