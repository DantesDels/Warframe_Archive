"""P1 connector contracts."""

from __future__ import annotations

import json
import unittest

from warframe_lore.v1.scraper.adapters.outbound.connectors.feed import FeedConnector
from warframe_lore.v1.scraper.adapters.outbound.connectors.mediawiki import (
    MediaWikiConnector,
)
from warframe_lore.v1.scraper.adapters.outbound.connectors.rest import RestConnector
from warframe_lore.v1.scraper.adapters.outbound.connectors.sitemap import (
    SitemapConnector,
)
from warframe_lore.v1.scraper.ports.outbound.sources import ConnectorContext


class _Resp:
    def __init__(self, content: bytes, content_type: str = "application/xml"):
        self.content = content
        self.status = 200
        self.from_cache = False
        self.url = "https://example.test"
        self.content_type = content_type
        self.encoding = "utf-8"


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
        pages = c.collect(
            {"location": "https://ex/sitemap.xml", "kind": "sitemap"}, ctx
        )
        self.assertEqual(pages[0].url, "https://ex/a")
        self.assertEqual(pages[0].metadata.get("lastmod"), "2026-01-01")

    def test_sitemap_connector_fetches_html_and_follows_sitemapindex(self):
        index_xml = (
            b"<sitemapindex><sitemap>"
            b"<loc>https://ex/sub.xml</loc></sitemap></sitemapindex>"
        )
        sub_xml = (
            b"<urlset><url><loc>https://ex/lore/1</loc>"
            b"<lastmod>2026-02-01</lastmod></url></urlset>"
        )
        html = (
            b"<html lang='en'><head><title>Chronicle</title></head>"
            b"<body><main><h2>Origins</h2><p>The first age began.</p></main></body>"
            b"</html>"
        )

        class MapClient:
            def get(self, url, **_kw):
                if url.endswith("sitemap.xml"):
                    return _Resp(index_xml, "application/xml")
                if url.endswith("sub.xml"):
                    return _Resp(sub_xml, "application/xml")
                return _Resp(html, "text/html")

        ctx = ConnectorContext(
            client=MapClient(), limits={"max_pages_per_source": 10}
        )
        pages = SitemapConnector().collect(
            {"location": "https://ex/sitemap.xml", "kind": "sitemap"}, ctx
        )
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].title, "Chronicle")
        self.assertIn("## Origins", pages[0].content)
        self.assertIn("The first age began.", pages[0].content)
        self.assertEqual(len(pages[0].metadata["sections"]), 1)

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
                    body = (
                        b'{"items":[{"id":1,"url":"https://ex/1"}],'
                        b'"next":"https://ex/api?page=2"}'
                    )
                    return _Resp(body)
                return _Resp(b'{"items":[{"id":2,"url":"https://ex/2"}]}')

        pages = RestConnector().collect(
            {"location": "https://ex/api", "kind": "api"},
            ConnectorContext(client=C(), limits={"max_pages_per_source": 10}),
        )
        self.assertEqual([p.url for p in pages], ["https://ex/1", "https://ex/2"])

    def test_mediawiki_root_url_batches_multiple_pages_not_just_main_page(self):
        class WikiClient:
            def __init__(self):
                self.calls = []

            def get(self, url, **kw):
                params = kw.get("params") or {}
                self.calls.append((url, dict(params)))
                if params.get("meta") == "siteinfo":
                    return _Resp(json.dumps(
                        {"query": {"general": {"mainpage": "Main Page"}}}
                    ).encode())
                if params.get("prop") == "links":
                    return _Resp(json.dumps(
                        {"query": {"pages": {"1": {"links": [{"title": "Lore"}]}}}}
                    ).encode())
                if params.get("list") == "allpages":
                    data = {"query": {"allpages": [
                        {"title": "Lore"}, {"title": "Quests"},
                    ]}}
                    return _Resp(json.dumps(data).encode())
                titles = str(params.get("titles", "")).split("|")
                pages = {
                    str(i + 1): {
                        "pageid": i + 1, "title": t,
                        "fullurl": f"https://wiki.example.com/wiki/{t}",
                        "categories": [{"title": "Category:Canon"}],
                        "revisions": [{
                            "revid": 10 + i,
                            "timestamp": "2026-01-01T00:00:00Z",
                            "slots": {"main": {"*": f"== {t} ==\nContent of {t}."}},
                        }],
                    }
                    for i, t in enumerate(titles)
                }
                return _Resp(json.dumps({"query": {"pages": pages}}).encode())

        client = WikiClient()
        ctx = ConnectorContext(client=client, limits={"max_pages_per_source": 10})
        pages = MediaWikiConnector().collect(
            {"location": "https://wiki.example.com/", "kind": "website"}, ctx
        )
        self.assertEqual([p.title for p in pages], ["Lore", "Quests"])
        batch_calls = [
            p for _, p in client.calls if str(p.get("prop", "")).startswith("extracts")
        ]
        self.assertEqual(len(batch_calls), 1)
        self.assertEqual(batch_calls[0]["titles"], "Lore|Quests")

    def test_mediawiki_auto_discovers_wikipedia_w_api_php(self):
        class WpClient:
            def __init__(self):
                self.urls = []

            def get(self, url, **kw):
                self.urls.append(url)
                params = kw.get("params") or {}
                if not url.endswith("/w/api.php"):
                    raise RuntimeError("404")
                if params.get("meta") == "siteinfo":
                    return _Resp(json.dumps(
                        {"query": {"general": {"mainpage": "Accueil"}}}
                    ).encode())
                return _Resp(json.dumps({"query": {"pages": {"5": {
                    "pageid": 5, "title": "Dune",
                    "fullurl": "https://fr.wikipedia.org/wiki/Dune",
                    "revisions": [{
                        "revid": 1,
                        "timestamp": "2026-01-01T00:00:00Z",
                        "slots": {"main": {"*": "== Univers ==\nArrakis."}},
                    }],
                }}}}).encode())

        client = WpClient()
        ctx = ConnectorContext(client=client, limits={"max_pages_per_source": 5})
        pages = MediaWikiConnector().collect(
            {"location": "https://fr.wikipedia.org/wiki/Dune", "kind": "website"}, ctx
        )
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].title, "Dune")
        self.assertTrue(all(u.endswith("/w/api.php") for u in client.urls))

    def test_mediawiki_category_url_crawls_subcategories(self):
        class CatClient:
            def get(self, url, **kw):
                params = kw.get("params") or {}
                if params.get("meta") == "siteinfo":
                    info = {"query": {"general": {"mainpage": "Main Page"}}}
                    return _Resp(json.dumps(info).encode())
                if params.get("list") == "categorymembers":
                    cm = params.get("cmtitle")
                    if cm == "Category:Lore":
                        return _Resp(json.dumps({"query": {"categorymembers": [
                            {"ns": 0, "title": "Era One"},
                            {"ns": 14, "title": "Category:SubLore"},
                        ]}}).encode())
                    return _Resp(json.dumps({"query": {"categorymembers": [
                        {"ns": 0, "title": "Era Two"},
                    ]}}).encode())
                titles = str(params.get("titles", "")).split("|")
                pages = {
                    str(i + 1): {
                        "pageid": i + 1, "title": t,
                        "fullurl": f"https://wiki.example.com/wiki/{t}",
                        "revisions": [{
                            "revid": i + 1,
                            "timestamp": "2026-01-01T00:00:00Z",
                            "slots": {"main": {"*": f"Text of {t}."}},
                        }],
                    }
                    for i, t in enumerate(titles)
                }
                return _Resp(json.dumps({"query": {"pages": pages}}).encode())

        ctx = ConnectorContext(
            client=CatClient(), limits={"max_pages_per_source": 10, "max_depth": 2}
        )
        pages = MediaWikiConnector().collect(
            {"location": "https://wiki.example.com/wiki/Category:Lore", "kind": "wiki"},
            ctx,
        )
        self.assertEqual([p.title for p in pages], ["Era One", "Era Two"])

    def test_html_connector_extracts_markdown_sections_and_filters_noise(self):
        from warframe_lore.v1.scraper.adapters.outbound.connectors.html import (
            HtmlConnector,
        )

        home = (
            b"<html lang='en'><head><title>Portal</title></head><body><main>"
            b"<h2>News</h2><p>Latest chronicles.</p>"
            b"<a href='/en/lore'>Lore</a>"
            b"<a href='/en/login'>Login</a>"
            b"<a href='/en/shop'>Shop</a>"
            b"<a href='/fr/lore'>FR</a>"
            b"</main></body></html>"
        )
        lore = (
            b"<html lang='en'><head><title>Lore</title></head><body><main>"
            b"<h2>Chapter One</h2><p>Deep archive text.</p></main></body></html>"
        )

        class SiteClient:
            def get(self, url, **_kw):
                body = lore if url.endswith("/en/lore") else home
                resp = _Resp(body, "text/html")
                resp.url = url
                return resp

        ctx = ConnectorContext(
            client=SiteClient(), limits={"max_pages_per_source": 10, "max_depth": 1}
        )
        pages = HtmlConnector().collect(
            {"location": "https://site.example.com/en", "kind": "website"}, ctx
        )
        self.assertEqual(
            [p.url for p in pages],
            ["https://site.example.com/en", "https://site.example.com/en/lore"],
        )
        self.assertIn("## Chapter One", pages[1].content)
        self.assertEqual(len(pages[1].metadata["sections"]), 1)

    def test_html_connector_filters_by_topic_tags_and_drops_template_urls(self):
        from warframe_lore.v1.scraper.adapters.outbound.connectors.html import (
            HtmlConnector,
        )

        home = (
            b"<html lang='en'><head><title>Home</title></head><body><main>"
            b"<a href='/en/{{url}}'>Bad</a>"
            b"<a href='/en/jedi-order'>Jedi</a>"
            b"<a href='/en/patch-fix'>Patch</a>"
            b"</main></body></html>"
        )
        jedi = (
            b"<html lang='en'><head><title>Jedi Order</title></head><body><main>"
            b"<h2>Jedi</h2><p>Guardians of peace.</p></main></body></html>"
        )
        patch = (
            b"<html lang='en'><head><title>Patch</title></head><body><main>"
            b"<p>Fixed audio bug.</p></main></body></html>"
        )

        class TagClient:
            def __init__(self):
                self.seen = []

            def get(self, url, **_kw):
                self.seen.append(url)
                body = jedi if "jedi" in url else (patch if "patch" in url else home)
                resp = _Resp(body, "text/html")
                resp.url = url
                return resp

        client = TagClient()
        ctx = ConnectorContext(
            client=client,
            limits={"max_pages_per_source": 10, "max_depth": 1, "topic_tags": ["Jedi"]},
        )
        pages = HtmlConnector().collect(
            {"location": "https://site.example.com/en", "kind": "website"}, ctx
        )
        self.assertFalse(any("{{" in u or "%7B" in u for u in client.seen))
        self.assertEqual(
            [p.url for p in pages],
            ["https://site.example.com/en", "https://site.example.com/en/jedi-order"],
        )
