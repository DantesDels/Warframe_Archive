"""Known Warframe sources for Atelier v1 bootstrap."""

from __future__ import annotations

from typing import Any, cast

from .collect.language import is_url_language_allowed
from .collect.language_purge import purge_disallowed_languages_and_duplicates

WARFRAME_SOURCES: list[dict[str, Any]] = [
    {
        "kind": "wiki",
        "location": "https://wiki.warframe.com/w/Category:Lore",
        "categories": ["Lore"],
        "proof": "Wiki officiel Warframe (EN) — Univers, histoire & fragments.",
    },
    {
        "kind": "wiki",
        "location": "https://wiki.warframe.com/w/Category:Quest",
        "categories": ["Quest"],
        "proof": "Wiki officiel Warframe (EN) — Quêtes principales et secondaires.",
    },
    {
        "kind": "wiki",
        "location": "https://wiki.warframe.com/w/Category:Characters",
        "categories": ["Characters"],
        "proof": "Wiki officiel Warframe (EN) — Personnages du lore.",
    },
    {
        "kind": "wiki",
        "location": "https://wiki.warframe.com/w/Category:Factions",
        "categories": ["Factions"],
        "proof": "Wiki officiel Warframe (EN) — Factions & cosmologie.",
    },
    {
        "kind": "wiki",
        "location": "https://wiki.warframe.com/w/Category:Quotes",
        "categories": ["Quotes"],
        "proof": "Wiki officiel Warframe (EN) — Dialogues, transcripts & citations.",
    },
    {
        "kind": "wiki",
        "location": "https://wiki.warframe.com/w/Kinemantik_Instant_Messenger",
        "prefix": "Kinemantik Instant Messenger/",
        "proof": "Wiki officiel Warframe (EN) — Dialogues du terminal KIM (1999).",
    },
    {
        "kind": "wiki",
        "location": "https://wiki.warframe.com/",
        "categories": ["Lore", "Quest", "Characters", "Factions", "Quotes"],
        "proof": "Wiki officiel Warframe (EN), source principale du projet.",
    },
    {
        "kind": "wiki",
        "location": "https://fr.wiki.warframe.com/",
        "categories": ["Lore", "Quêtes", "Personnages", "Factions", "Citations"],
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
        "kind": "api",
        "location": "https://origin.warframe.com/PublicExport/index_en.txt.lzma",
        "manifest_base_url": "http://content.warframe.com/PublicExport/Manifest/",
        "proof": "Index Public Export officiel Digital Extremes.",
    },
]


def seed_warframe_sources(
    workspace: Any, allowed_languages: tuple[str, ...] = ("en",)
) -> int:
    """Add missing known Warframe sources matching allowed_languages (default EN)."""
    universe = _find_warframe(workspace)
    if universe is None:
        return 0
    uid = str(universe["id"])
    caps = (
        workspace.capabilities_for(uid)
        if hasattr(workspace, "capabilities_for")
        else {}
    )
    langs = caps.get("allowed_languages") or allowed_languages
    added = 0
    for source in WARFRAME_SOURCES:
        if not is_url_language_allowed(source["location"], langs):
            continue
        if _has_location(workspace, uid, source["location"]):
            _set_proof(workspace, uid, source)
            continue
        workspace.add_manual_source(uid, source["location"], kind=source["kind"])
        _set_proof(workspace, uid, source)
        added += 1
    if len(cast(list[Any], workspace.sources_for(uid))) > 20:
        purge_disallowed_languages_and_duplicates(workspace, uid, langs)
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


def _set_proof(workspace: Any, universe_id: str, seed: dict[str, Any]) -> None:
    needle = str(seed["location"]).rstrip("/").casefold()
    sources = cast(list[dict[str, Any]], workspace.data.get("sources", []))
    for source in sources:
        same = str(source.get("location", "")).rstrip("/").casefold() == needle
        if same and str(source.get("universeId")) == universe_id:
            source["proof"] = str(seed.get("proof", ""))
            source["kind"] = str(seed.get("kind", source.get("kind", "website")))
            if seed.get("categories"):
                source["categories"] = list(seed["categories"])
            if seed.get("prefix"):
                source["prefix"] = str(seed["prefix"])
            if seed.get("manifest_base_url"):
                source["manifest_base_url"] = str(seed["manifest_base_url"])
            source["discoveredBy"] = "catalogue-warframe"
            source["score"] = 1.0
            return
