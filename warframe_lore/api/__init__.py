"""API layer: access to data sources (extraction).

Exposes:
    * :class:`BaseSource` — abstract interface for any source;
    * :class:`MediaWikiSource` — Warframe wiki implementation;
    * :class:`BucketConfig` / :class:`CategoryCatalog` — bucket resolution.
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
from .site_html import SiteHtmlSource

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
    "SiteHtmlSource",
]
