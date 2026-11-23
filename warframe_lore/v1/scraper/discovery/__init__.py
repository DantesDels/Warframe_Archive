"""Discovery adapters for the v1 scraping workshop."""

from __future__ import annotations

from .models import CANDIDATE_STATUSES, DISCOVERY_PROVIDERS, Candidate
from .providers import KeywordProvider, build_default_providers
from .service import discover, keywords_for

__all__ = [
    "CANDIDATE_STATUSES",
    "DISCOVERY_PROVIDERS",
    "Candidate",
    "KeywordProvider",
    "build_default_providers",
    "discover",
    "keywords_for",
]
