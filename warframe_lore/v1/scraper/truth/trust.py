"""Source trust profiles (Official, Documentation, Community Wiki, Third-party)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

TRUST_PROFILES: dict[str, tuple[str, float]] = {
    "official": ("Officiel", 1.0),
    "documentation": ("Documentation", 0.85),
    "community_wiki": ("Wiki communautaire", 0.70),
    "third_party": ("Tiers", 0.45),
}
TRUST_PROFILE_ORDER = ("official", "documentation", "community_wiki", "third_party")

_DOC_HINTS = ("docs.", "readthedocs", "developer.", "/docs/", "/api/", "manual")
_WIKI_HINTS = ("wiki", "fandom.com", "wikipedia.org", "liquipedia", "pedia")


def trust_label(profile: str) -> str:
    """Return the French display label for a trust profile key."""
    return TRUST_PROFILES.get(profile, TRUST_PROFILES["third_party"])[0]


def trust_weight(profile: str) -> float:
    """Return the numeric authority weight in [0, 1] for a trust profile."""
    return TRUST_PROFILES.get(profile, TRUST_PROFILES["third_party"])[1]


def infer_trust_profile(
    source: dict[str, Any] | None = None, url: str = ""
) -> str:
    """Resolve explicit or heuristic trust profile for a source or URL."""
    src = source or {}
    explicit = str(src.get("trustProfile") or "").strip().lower()
    if explicit in TRUST_PROFILES:
        return explicit

    target = str(url or src.get("location") or "").strip().lower()
    host = urlparse(target).netloc if "://" in target else ""
    combined = f"{host} {target}"
    if any(hint in combined for hint in _WIKI_HINTS):
        return "community_wiki"
    if any(hint in combined for hint in _DOC_HINTS):
        return "documentation"

    kind = str(src.get("kind") or "").strip().lower()
    relevance = float(src.get("relevance") or 0.0)
    if kind in {"api", "document"} or relevance >= 0.85:
        return "official"
    return "third_party"


def set_source_trust_profile(
    workspace: Any, source_id: str, profile: str
) -> bool:
    """Persist an explicit trust profile on a source in the workspace."""
    if profile not in TRUST_PROFILES:
        raise ValueError(f"Unknown trust profile: {profile}")
    for source in workspace.data.get("sources", []):
        if str(source.get("id")) == source_id:
            source["trustProfile"] = profile
            if hasattr(workspace, "save"):
                workspace.save()
            return True
    return False
