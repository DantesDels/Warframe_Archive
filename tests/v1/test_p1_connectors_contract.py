"""P1 connector contracts."""

from __future__ import annotations

import unittest

from warframe_lore.v1.scraper.adapters.outbound.connectors.feed import FeedConnector
from warframe_lore.v1.scraper.adapters.outbound.connectors.rest import RestConnector
from warframe_lore.v1.scraper.adapters.outbound.connectors.sitemap import (
    SitemapConnector,
)
from warframe_lore.v1.scraper.ports.outbound.sources import ConnectorContext


class _Resp:
    def __init__(self, content: bytes):
        self.content = content
        self.status = 200
        self.from_cache = False
        self.url = "https://example.test"
        self.content_type = "application/xml"


class _Client:
    def __init__(self, payload: bytes):
        self.payload = payload

    def get(self, *_a, **_kw):
        return _Resp(self.payload)


class ConnectorContractTests(unittest.TestCase):
    def test_sitemap_connector_parses_lastmod(self):
        xml = (
            b"<urlset><url><loc>https://ex/a</loc>"
            b"<lastmod>2026-01-01</lastmod></url></urlset>"
        )
        c = SitemapConnector()
        ctx = ConnectorContext(
            client=_Client(xml),
            limits={"incremental": True, "max_pages_per_source": 10},
        )
        pages = c.collect({"location": "https://ex/sitemap.xml", "kind": "sitemap"},
            ctx)
        self.assertEqual(pages[0].url, "https://ex/a")
        self.assertEqual(pages[0].metadata.get("lastmod"), "2026-01-01")

    def test_feed_connector_parses_entries(self):
        xml = (
            b"<rss><channel><item><title>T</title>"
            b"<link>https://ex/p</link></item></channel></rss>"
        )
        pages = FeedConnector().collect(
            {"location": "https://ex/feed.xml"},
            ConnectorContext(client=_Client(xml), limits={}),
        )
        self.assertEqual(pages[0].url, "https://ex/p")

    def test_rest_connector_paginates(self):
        class C:
            def __init__(self):
                self.n = 0

            def get(self, url, **_kw):
                self.n += 1
                if self.n == 1:
                    return _Resp(b'{"items":[{"id":1,"url":"https://ex/1"}],"next":"https://ex/api?page=2"}')
                return _Resp(b'{"items":[{"id":2,"url":"https://ex/2"}]}')

        pages = RestConnector().collect(
            {"location": "https://ex/api", "kind": "api"},
            ConnectorContext(client=C(), limits={"max_pages_per_source": 10}),
        )
        self.assertEqual([p.url for p in pages], ["https://ex/1", "https://ex/2"])
