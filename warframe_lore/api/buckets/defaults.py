"""Buckets logiques par défaut (alignés sur le cahier des charges).

Le wiki officiel n'utilise pas exactement les noms du cahier des charges
(``Quests``, ``Kinemantik_Instant_Messenger``, ``Fables_&_Frontiers``, ...).
Ses catégories réelles sont :
  * Quêtes        -> ``Quest`` (+ ``Replayable Quests`` / ``Not Replayable Quests``)
  * Personnages   -> ``Characters``
  * Factions      -> ``Factions``
  * Citations     -> ``Quotes`` (429 pages : voix, transcripts, KIM, F&F)
  * Lore générale -> ``Lore``

L'ordre compte : une page est réclamée par le PREMIER bucket qui l'accepte,
ce qui évite les doublons entre megafiles.
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