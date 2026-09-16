"""Default logical buckets (aligned with the project specification).

The official wiki does not use exactly the names from the specification
(``Quests``, ``Kinemantik_Instant_Messenger``, ``Fables_&_Frontiers``, ...).
Its real categories are:
  * Quests        -> ``Quest`` (+ ``Replayable Quests`` / ``Not Replayable Quests``)
  * Characters    -> ``Characters``
  * Factions      -> ``Factions``
  * Quotes        -> ``Quotes`` (429 pages: voices, transcripts, KIM, F&F)
  * General lore  -> ``Lore``

Order matters: a page is claimed by the FIRST bucket that accepts it,
which avoids duplicates between megafiles.
"""

from __future__ import annotations

from ..models import CategorySpec

DEFAULT_BUCKETS: list[CategorySpec] = [
    CategorySpec(
        id="Lore_Quetes",
        title="Quêtes",
        filename="Lore_Quetes.json",
        categories=["Quest"],
        title_exclude=["/Transcript"],
    ),
    CategorySpec(
        id="Lore_Dialogues_Quetes",
        title="Dialogues de quêtes",
        filename="Lore_Dialogues_Quetes.json",
        categories=["Quotes"],
        title_include=["/Transcript"],
    ),
    CategorySpec(
        id="Lore_Dialogues_KIM",
        title="Terminal KIM",
        filename="Lore_Dialogues_KIM.json",
        categories=["Quotes"],
        prefix=["Kinemantik Instant Messenger/"],
        title_include=["Kinemantik Instant Messenger", "Fables & Frontiers"],
        title_exclude=["The Hex", "SectionList"],
    ),
    CategorySpec(
        id="Lore_Characters",
        title="Personnages",
        filename="Lore_Characters.json",
        categories=["Characters"],
        title_exclude=["/Quotes", "/Transcript", "/KIM"],
    ),
    CategorySpec(
        id="Lore_Dialogues_Quotes",
        title="Lignes de dialogue",
        filename="Lore_Dialogues_Quotes.json",
        categories=["Quotes"],
        title_include=["/Quotes"],
    ),
    CategorySpec(
        id="Lore_Cosmologie_Factions",
        title="Factions & cosmologie",
        filename="Lore_Cosmologie_Factions.json",
        categories=["Factions"],
    ),
    CategorySpec(
        id="Lore_Fragments",
        title="Fragments",
        filename="Lore_Fragments.json",
        categories=["Lore"],
        title_include=["Fragment"],
    ),
    CategorySpec(
        id="Lore_Univers_Histoire",
        title="Univers, cosmologie & histoire",
        filename="Lore_Univers_Histoire.json",
        categories=["Lore"],
        title_exclude=["/Quotes", "/Transcript", "/KIM", "Kinemantik",
                       "Fables & Frontiers", "Fragment"],
    ),
    CategorySpec(
        id="Lore_Site_Officiel_FR",
        title="Site officiel (FR)",
        filename="Lore_Site_Officiel_FR.json",
        source="warframe-com-fr",
        categories=["/fr"],
        title_include=["/fr"],
        title_exclude=["/shop", "/prime-", "/supporter", "/download",
                       "/zendesk", "/promocode", "/signup", "/login",
                       "/account", "/gemini", "/heirloom", "/code"],
    ),
    # ---- English-language archives (truth authority on conflicts) ----
    CategorySpec(
        id="Lore_Site_Officiel_EN",
        title="Site officiel (EN)",
        filename="Lore_Site_Officiel_EN.json",
        source="warframe-com-en",
        categories=["/en"],
        title_include=["/en"],
        title_exclude=["/shop", "/prime-", "/supporter", "/download",
                       "/zendesk", "/promocode", "/signup", "/login",
                       "/account", "/gemini", "/heirloom", "/code"],
    ),
    # ---- French wiki mirror (fr.wiki.warframe.com) ----
    CategorySpec(
        id="Lore_Quetes_FR",
        title="Quêtes (wiki FR)",
        filename="Lore_Quetes_FR.json",
        source="mediawiki-warframe-fr",
        categories=["Quêtes"],
        title_exclude=["/Transcript"],
    ),
    CategorySpec(
        id="Lore_Characters_FR",
        title="Personnages (wiki FR)",
        filename="Lore_Characters_FR.json",
        source="mediawiki-warframe-fr",
        categories=["Personnages"],
        title_exclude=["/Quotes", "/Citations", "/Transcript", "/KIM"],
    ),
    CategorySpec(
        id="Lore_Dialogues_Quotes_FR",
        title="Lignes de dialogue (wiki FR)",
        filename="Lore_Dialogues_Quotes_FR.json",
        source="mediawiki-warframe-fr",
        categories=["Citations"],
        title_include=["/Citations", "/Quotes"],
    ),
    CategorySpec(
        id="Lore_Cosmologie_Factions_FR",
        title="Factions & cosmologie (wiki FR)",
        filename="Lore_Cosmologie_Factions_FR.json",
        source="mediawiki-warframe-fr",
        categories=["Factions"],
    ),
    CategorySpec(
        id="Lore_Fragments_FR",
        title="Fragments (wiki FR)",
        filename="Lore_Fragments_FR.json",
        source="mediawiki-warframe-fr",
        categories=["Lore"],
        title_include=["Fragment"],
    ),
    CategorySpec(
        id="Lore_Univers_Histoire_FR",
        title="Univers & histoire (wiki FR)",
        filename="Lore_Univers_Histoire_FR.json",
        source="mediawiki-warframe-fr",
        categories=["Lore"],
        title_exclude=["/Quotes", "/Transcript", "/KIM", "Fragment"],
    ),
]
