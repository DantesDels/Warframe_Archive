"""Buckets logiques : définition, configuration et résolution.

Sous-paquet regroupant ce qui concerne la notion de "bucket" (groupement
logique de pages source -> megafile de sortie) :
    * ``defaults`` — les 8 buckets par défaut ;
    * ``config``   — chargement/sauvegarde de ``buckets.json`` ;
    * ``catalog``  — résolution des catégories + affectation des pages.
"""

from __future__ import annotations

from .catalog import CategoryCatalog, ResolvedBucket, assign_pages
from .config import BucketConfig
from .defaults import DEFAULT_BUCKETS

__all__ = [
    "DEFAULT_BUCKETS",
    "BucketConfig",
    "CategoryCatalog",
    "ResolvedBucket",
    "assign_pages",
]