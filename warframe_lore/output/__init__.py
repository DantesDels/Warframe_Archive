"""Couche Output : écriture des megafiles JSON pour les consommateurs.

Le schéma de chaque entrée inclut ``canon_status`` pour permettre au RAG /
aux notebooks de filtrer le lore officiel des théories des joueurs.
"""

from .models import (
    CanonStatus,
    MegafileMetadata,
    OutputEntry,
    build_output_entry,
    merge_canon_status,
)
from .writer import MegafileManager

__all__ = [
    "CanonStatus",
    "MegafileMetadata",
    "OutputEntry",
    "build_output_entry",
    "merge_canon_status",
    "MegafileManager",
]
