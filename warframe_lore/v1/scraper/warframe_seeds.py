"""Known Warframe sources for Atelier v1 bootstrap."""

from __future__ import annotations

WARFRAME_SOURCES = [
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
        "proof": "Site officiel Warframe (EN), pages publiques et actualit?s.",
    },
    {
        "kind": "website",
        "location": "https://www.warframe.com/fr",
        "proof": "Site officiel Warframe (FR), pages publiques et actualit?s.",
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


def seed_warframe_sources(workspace) -> int:
    """Add missing known Warframe sources to the Warframe universe."""
    universe = _find_warframe(workspace)
    if universe is None:
        return 0
    added = 0
    for source in WARFRAME_SOURCES:
        if _has_location(workspace, universe["id"], source["location"]):
            continue
        workspace.add_manual_source(
            universe["id"], source["location"], kind=source["kind"]
        )
        _set_proof(workspace, universe["id"], source["location"], source["proof"])
        added += 1
    if added:
        workspace.save()
    return added


def _find_warframe(workspace):
    for universe in workspace.universes():
        uid = str(universe.get("id", "")).casefold()
        name = str(universe.get("name", "")).casefold()
        if uid == "warframe" or name == "warframe":
            return universe
    return None


def _has_location(workspace, universe_id: str, location: str) -> bool:
    needle = location.rstrip("/").casefold()
    return any(
        str(s.get("location", "")).rstrip("/").casefold() == needle
        and s.get("universeId") == universe_id
        for s in workspace.data.get("sources", [])
    )


def _set_proof(workspace, universe_id: str, location: str, proof: str) -> None:
    needle = location.rstrip("/").casefold()
    for source in workspace.data.get("sources", []):
        same = str(source.get("location", "")).rstrip("/").casefold() == needle
        if same and source.get("universeId") == universe_id:
            source["proof"] = proof
            source["discoveredBy"] = "catalogue-warframe"
            source["score"] = 1.0
            return
