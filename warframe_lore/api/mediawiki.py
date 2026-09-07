"""Source MediaWiki (wiki.warframe.com) — composition des mixins.

La classe ``MediaWikiSource`` est le point d'entrée public de la source
MediaWiki ; elle compose par héritage multiple :
    * ``MediaWikiCategoryMixin`` — résolution catégories/préfixes ;
    * ``MediaWikiQueryMixin``    — fetch contenu + métadonnées delta ;
    * ``BaseSource``             — contrat abstrait de toute source.

Le transport HTTP (retries/backoff/throttle) vit dans ``http``.
"""

from __future__ import annotations

from .base import BaseSource
from .http import RetryableHttp
from .mediawiki_categories import MediaWikiCategoryMixin
from .mediawiki_queries import MediaWikiQueryMixin


class MediaWikiSource(MediaWikiCategoryMixin, MediaWikiQueryMixin, BaseSource):
    """Source de données officielle de Warframe (wiki.warframe.com)."""

    name = "mediawiki-warframe"

    def __init__(self, config) -> None:
        self.config = config
        self.http = RetryableHttp(
            api_url=config.api_url,
            user_agent=config.user_agent,
            timeout=config.request_timeout,
            max_retries=config.max_retries,
            retry_backoff=config.retry_backoff,
            min_sleep=config.min_sleep_between_requests,
            per_request_limit=config.per_request_limit,
        )