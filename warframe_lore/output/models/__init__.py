"""Output layer models -- one file per class.

    * ``canon_status``      -> :class:`CanonStatus` (+ ``merge_canon_status``);
    * ``output_entry``      -> :class:`OutputEntry`;
    * ``megafile_metadata`` -> :class:`MegafileMetadata`.

The package re-exports the public API to preserve legacy imports
(``from warframe_lore.output.models import ...``).
"""

from __future__ import annotations

from .canon_status import CanonStatus, merge_canon_status
from .megafile_metadata import MegafileMetadata
from .output_entry import OutputEntry

__all__ = [
    "CanonStatus",
    "MegafileMetadata",
    "OutputEntry",
    "merge_canon_status",
]
