"""Facade for the MediaWiki client — preserves legacy imports.

The implementation has been split between ``mediawiki`` (source
composition), ``mediawiki_queries``, ``mediawiki_categories`` and ``http``
(transport).  This module re-exports what historically lived here.
"""

from __future__ import annotations

from .http import MediaWikiSourceError, RetryableHttp
from .mediawiki import MediaWikiSource

__all__ = ["MediaWikiSource", "RetryableHttp", "MediaWikiSourceError"]