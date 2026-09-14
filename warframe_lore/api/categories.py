"""Facade for bucket resolution — preserves legacy imports.

The logic has been split into the ``buckets`` sub-package (``defaults``,
``config``, ``catalog``).  The former ``Categories`` API re-exports the
public symbols here so existing imports keep working.
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
