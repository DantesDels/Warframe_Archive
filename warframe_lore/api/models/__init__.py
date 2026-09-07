"""Modèles de données source-agnostics — un fichier par classe.

Ces dataclasses décrivent le contrat de données entre les couches
(API -> scraper -> cleaner -> output), quel que soit le fournisseur
(MediaWiki aujourd'hui, Reddit/Forums demain).

    * ``page_data``      -> :class:`PageData` ;
    * ``touched_info``   -> :class:`TouchedInfo` ;
    * ``category_spec``  -> :class:`CategorySpec`.
"""

from __future__ import annotations

from .category_spec import CategorySpec
from .page_data import PageData
from .touched_info import TouchedInfo

__all__ = ["CategorySpec", "PageData", "TouchedInfo"]