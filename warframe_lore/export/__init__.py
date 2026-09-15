"""Warframe Public Export -- ingestion of localized game entities.

Official pipeline (see wiki.warframe.com/w/Public_Export):
  1. ``https://origin.warframe.com/PublicExport/index_<lang>.txt.lzma``  -> a
     **raw** LZMA stream containing hashed manifest names (one per line,
     format ``Export<Category>_<lang>.json!00_<hash>``).
  2. For each hashed name, the asset is served by the content server:
     ``http://content.warframe.com/PublicExport/Manifest/<hashed_name>``.
     The asset is a JSON like ``{"Export<Category>": [ {uniqueName, name,
     description, ...}, ... ]}``.

The cache is **incremental and safe**: the ``!00_<hash>`` hash
(content-addressed) changes only when the content changes -- an asset
already downloaded can be kept indefinitely and we re-sync by comparing
index hashes.

Package layout:
    * ``const``    -> constants (origins, languages, selected categories);
    * ``lzma``     -> LZMA decompression tolerant of truncated streams;
    * ``assets``   -> asset validation + field normalization;
    * ``extract``  -> localized entity extraction;
    * ``fetch``    -> hashed index + assets (incremental cache);
    * ``sync``     -> async database synchronization loop;
    * ``client``   -> :class:`PublicExportClient` (facade);
    * ``models``   -> :class:`GameEntity` (one file per class).
"""

from __future__ import annotations

from .client import PublicExportClient
from .const import DEFAULT_LANGS, EXPORT_CATEGORIES
from .lzma import decompress_lzma
from .models import GameEntity

__all__ = [
    "DEFAULT_LANGS",
    "EXPORT_CATEGORIES",
    "GameEntity",
    "PublicExportClient",
    "decompress_lzma",
]
