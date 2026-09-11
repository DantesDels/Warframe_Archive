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
]