"""Known Warframe sources for Atelier v1 bootstrap."""

from __future__ import annotations

from typing import Any, cast

WARFRAME_SOURCES: list[dict[str, str]] = [
    {
        "kind": "website",
        "location": "https://wiki.warframe.com/",
        "proof": "Wiki officiel Warframe (EN), source principale du projet.",
    },
    {
        "kind": "website",
        "location": "https://fr.wiki.warframe.com/",
        "proof": "Wiki officiel Warframe (FR), archive de corroboration.",
    },
    {
        "kind": "website",
        "location": "https://www.warframe.com/en",
        "proof": "Site officiel Warframe (EN), pages publiques et actualités.",
    },
    {
        "kind": "website",
        "location": "https://www.warframe.com/fr",
        "proof": "Site officiel Warframe (FR), pages publiques et actualités.",
    },
    {
        "kind": "website",
        "location": "https://forums.warframe.com/",
        "proof": "Forums officiels Warframe pour annonces et discussions.",
    },
    {
        "kind": "api",
        "location": "https://origin.warframe.com/PublicExport/index_en.txt.lzma",
        "proof": "Index Public Export officiel Digital Extremes.",
    },
]


def seed_warframe_sources(workspace: Any) -> int:
    """Add missing known Warframe sources to the Warframe universe."""
    universe = _find_warframe(workspace)
    if universe is None:
        return 0
    added = 0
    for source in WARFRAME_SOURCES:
        if _has_location(workspace, str(universe["id"]), source["location"]):
            continue
        workspace.add_manual_source(
            str(universe["id"]), source["location"], kind=source["kind"]
        )
        _set_proof(
            workspace, str(universe["id"]), source["location"], source["proof"]
        )
        added += 1
    if added:
        workspace.save()
    return added


def _find_warframe(workspace: Any) -> dict[str, Any] | None:
    for universe in cast(list[dict[str, Any]], workspace.universes()):
        uid = str(universe.get("id", "")).casefold()
        name = str(universe.get("name", "")).casefold()
        if uid == "warframe" or name == "warframe":
            return universe
    return None


def _has_location(workspace: Any, universe_id: str, location: str) -> bool:
    needle = location.rstrip("/").casefold()
    sources = cast(list[dict[str, Any]], workspace.data.get("sources", []))
    return any(
        str(s.get("location", "")).rstrip("/").casefold() == needle
        and str(s.get("universeId")) == universe_id
        for s in sources
    )


def _set_proof(workspace: Any, universe_id: str, location: str, proof: str) -> None:
    needle = location.rstrip("/").casefold()
    sources = cast(list[dict[str, Any]], workspace.data.get("sources", []))
    for source in sources:
        same = str(source.get("location", "")).rstrip("/").casefold() == needle
        if same and str(source.get("universeId")) == universe_id:
            source["proof"] = proof
            source["discoveredBy"] = "catalogue-warframe"
            source["score"] = 1.0
            return
