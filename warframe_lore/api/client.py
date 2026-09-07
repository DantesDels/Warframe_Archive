"""Façade du client MediaWiki — préserve les imports historiques.

L'implémentation a été éclatée entre ``mediawiki`` (composition de la
source), ``mediawiki_queries``, ``mediawiki_categories`` et ``http``
(transport).  Ce module ré-exporte ce qui vivait historiquement ici.
"""

from __future__ import annotations

from .http import MediaWikiSourceError, RetryableHttp
from .mediawiki import MediaWikiSource

__all__ = ["MediaWikiSource", "RetryableHttp", "MediaWikiSourceError"]