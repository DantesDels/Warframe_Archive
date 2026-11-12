"""MediaWiki source (wiki.warframe.com) — mixin composition.

The ``MediaWikiSource`` class is the public entry point of the MediaWiki
source; it composes through multiple inheritance:
    * ``MediaWikiCategoryMixin`` — category/prefix resolution;
    * ``MediaWikiQueryMixin``    — content fetch + delta metadata;
    * ``BaseSource``             — abstract contract of any source.

The HTTP transport (retries/backoff/throttle) lives in ``http``.
"""

from __future__ import annotations

from .base import BaseSource
from .http import RetryableHttp
from .mediawiki_categories import MediaWikiCategoryMixin
from .mediawiki_queries import MediaWikiQueryMixin


class MediaWikiSource(MediaWikiCategoryMixin, MediaWikiQueryMixin, BaseSource):
    """Official Warframe data source (wiki.warframe.com)."""

    name = "mediawiki-warframe"

    def __init__(self, config, *, api_url: str | None = None,
                 category_label: str = "Category:", name: str | None = None):
        self.config = config
        self.name = name or type(self).name
        self.category_label = category_label
        self.http = RetryableHttp(
            api_url=api_url or config.api_url,
            user_agent=config.user_agent,
            timeout=config.request_timeout,
            max_retries=config.max_retries,
            retry_backoff=config.retry_backoff,
            min_sleep=config.min_sleep_between_requests,
            per_request_limit=config.per_request_limit,
        )
