"""Declarative connector registry."""

from __future__ import annotations

from typing import Any, cast

from ....ports.outbound.sources import ConnectorContext, SourceConnectorPort


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: list[SourceConnectorPort] = []

    def register(self, connector: SourceConnectorPort) -> None:
        self._connectors.append(cast(SourceConnectorPort, connector))

    def resolve(
        self, source: dict[str, Any], ctx: ConnectorContext
    ) -> SourceConnectorPort:
        for connector in self._connectors:
            if connector.can_handle(source, ctx):
                return connector
        raise ValueError(f"No connector for source: {source.get('location')!r}")


def default_registry() -> ConnectorRegistry:
    from ....json_collection.connector import GithubDirectoryConnector
    from .document import DocumentConnector
    from .feed import FeedConnector
    from .html import HtmlConnector
    from .local_directory import LocalDirectoryConnector
    from .lzma import LzmaConnector
    from .mediawiki import MediaWikiConnector
    from .multimodal import MultimodalConnector
    from .playwright import PlaywrightConnector
    from .rest import RestConnector
    from .sitemap import SitemapConnector

    registry = ConnectorRegistry()
    connectors = (
        LocalDirectoryConnector(),
        GithubDirectoryConnector(),
        MultimodalConnector(),
        DocumentConnector(),
        LzmaConnector(),
        SitemapConnector(),
        FeedConnector(),
        MediaWikiConnector(),
        RestConnector(),
        PlaywrightConnector(),
        HtmlConnector(),
    )
    for connector in connectors:
        registry.register(cast(SourceConnectorPort, connector))
    return registry
