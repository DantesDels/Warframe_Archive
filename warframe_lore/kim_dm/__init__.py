"""Datamine du Terminal KIM — miroir + reconstruction des conversations.

Le paquet expose la façade du module historique ``kim_dm`` :

    * ``mirror_kim_dm``      : télécharge et met en cache le miroir GitHub ;
    * ``parse_dialogue_file``: conversations complètes d'un fichier natif ;
    * ``KimDM``              : accès en mémoire (conversations/graphes) ;
    * ``_anchor_graph``      : ancre synthétique (pages agrégées / wiki) ;
    * ``WIKI_PAGE_MAP``      : correspondance page wiki -> fichier datamine.

Sous-modules : ``constants`` (mappings moteur/URL), ``mirror``
(téléchargement + cache), ``graph`` (ancre/union), ``parser`` (nœuds natifs
-> conversations), ``traversal`` (projections graphe/messages/script),
``store`` (KimDM).
"""

from __future__ import annotations

from warframe_lore.kim_dm.constants import (
    BRANCH,
    DATA_DIRNAME,
    DIALECT_FILE_PREFIX,
    DIALOGUE_FILES,
    DICTS_DIRNAME,
    RAW_BASE,
    REPO,
    SUPPORTED_LANGS,
    WIKI_PAGE_MAP,
)
from warframe_lore.kim_dm.graph import _anchor_graph, _merge_graphs
from warframe_lore.kim_dm.mirror import mirror_kim_dm
from warframe_lore.kim_dm.parser import parse_dialogue_file
from warframe_lore.kim_dm.store import KimDM

__all__ = [
    "KimDM",
    "WIKI_PAGE_MAP",
    "parse_dialogue_file",
    "mirror_kim_dm",
]