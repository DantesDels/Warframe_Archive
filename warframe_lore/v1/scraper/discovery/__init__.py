"""Discovery adapters for the v1 scraping workshop."""

from __future__ import annotations

from .models import CANDIDATE_STATUSES, Candidate
from .providers import KeywordProvider
from .service import discover, keywords_for

__all__ = [
    "CANDIDATE_STATUSES",
    "Candidate",
    "KeywordProvider",
    "discover",
    "keywords_for",
]
