"""Logical buckets: definition, configuration and resolution.

Sub-package regrouping everything about the "bucket" notion (logical
grouping of source pages -> output megafile):
    * ``defaults`` — the 8 default buckets;
    * ``config``   — load/save of ``buckets.json``;
    * ``catalog``  — category resolution + page assignment.
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