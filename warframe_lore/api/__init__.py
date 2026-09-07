"""Couche API : accès aux sources de données (extraction).

Expose :
    * :class:`BaseSource` — interface abstraite pour toute source ;
    * :class:`MediaWikiSource` — implémentation du wiki Warframe ;
    * :class:`BucketConfig` / :class:`CategoryCatalog` — résolution des buckets.
"""

from .base import BaseSource, CategorySpec, PageData, TouchedInfo
from .buckets import (
    DEFAULT_BUCKETS,
    BucketConfig,
    CategoryCatalog,
    ResolvedBucket,
    assign_pages,
)
from .client import MediaWikiSource

__all__ = [
    "BaseSource",
    "CategorySpec",
    "PageData",
    "TouchedInfo",
    "DEFAULT_BUCKETS",
    "BucketConfig",
    "CategoryCatalog",
    "ResolvedBucket",
    "assign_pages",
    "MediaWikiSource",
]
