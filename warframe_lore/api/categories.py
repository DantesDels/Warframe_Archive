"""Façade de la résolution des buckets — préserve les imports historiques.

La logique a été éclatée dans le sous-paquet ``buckets`` (``defaults``,
``config``, ``catalog``).  L'ancienne API ``Categories`` ré-exporte ici les
symboles publics pour ne pas casser les imports existants.
"""

from __future__ import annotations

from .buckets import (
    DEFAULT_BUCKETS,
    BucketConfig,
    CategoryCatalog,
    ResolvedBucket,
    assign_pages,
)

__all__ = [
    "DEFAULT_BUCKETS",
    "BucketConfig",
    "CategoryCatalog",
    "ResolvedBucket",
    "assign_pages",
]