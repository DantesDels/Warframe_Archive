"""Source-agnostic data models — one file per class.

These dataclasses describe the data contract between the layers
(API -> scraper -> cleaner -> output), regardless of the provider
(MediaWiki today, Reddit/Forums tomorrow).

    * ``page_data``      -> :class:`PageData`;
    * ``touched_info``   -> :class:`TouchedInfo`;
    * ``category_spec``  -> :class:`CategorySpec`.
"""

from __future__ import annotations

from .category_spec import CategorySpec
from .page_data import PageData
from .touched_info import TouchedInfo

__all__ = ["CategorySpec", "PageData", "TouchedInfo"]
