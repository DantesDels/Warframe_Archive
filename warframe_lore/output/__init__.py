"""Output layer: JSON megafile writing for consumers.

Each entry's schema includes ``canon_status`` to allow RAG / notebooks
to filter official lore from player theories.
"""

from .models import (
    CanonStatus,
    MegafileMetadata,
    OutputEntry,
    merge_canon_status,
)
from .entries import build_output_entry
from .writer import MegafileManager

__all__ = [
    "CanonStatus",
    "MegafileMetadata",
    "OutputEntry",
    "build_output_entry",
    "merge_canon_status",
    "MegafileManager",
]
