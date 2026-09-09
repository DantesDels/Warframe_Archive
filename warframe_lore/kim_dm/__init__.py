"""KIM Terminal datamine — mirror + conversation reconstruction.

The package exposes the facade of the legacy ``kim_dm`` module:

    * ``mirror_kim_dm``      : downloads and caches the GitHub mirror;
    * ``parse_dialogue_file``: full conversations from a native file;
    * ``KimDM``              : in-memory access (conversations/graphs);
    * ``_anchor_graph``      : synthetic anchor (aggregated / wiki pages);
    * ``WIKI_PAGE_MAP``      : wiki page -> datamine file mapping.

Sub-modules: ``constants`` (engine/URL mappings), ``mirror``
(download + cache), ``graph`` (anchor/union), ``parser`` (native nodes
-> conversations), ``traversal`` (graph/messages/script projections),
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