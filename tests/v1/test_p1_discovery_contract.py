"""P1 discovery contracts: configurable providers, scoring, dedupe, limits."""

from __future__ import annotations

import unittest

from warframe_lore.v1.scraper.discovery import discover
from warframe_lore.v1.scraper.discovery.models import Candidate
from warframe_lore.v1.scraper.discovery.providers import build_default_providers
from warframe_lore.v1.scraper.discovery.providers.feed import FeedProvider
from warframe_lore.v1.scraper.discovery.providers.sitemap import SitemapProvider
from warframe_lore.v1.scraper.discovery.providers.web_search import WebSearchProvider


class _Resp:
    def __init__(self, status: int, content: bytes):
        self.status = status
        self.content = content


class _Client:
    def __init__(self, payloads: dict[str, tuple[int, bytes]]):
        self.payloads = payloads

    def get(self, url: str, **_kwargs):
        status, body = self.payloads.get(url, (404, b""))
        return _Resp(status, body)


class P1DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.universe = {"id": "u1", "name": "Codex", "description": "fantasy"}

    def test_web_search_provider_opt_in_endpoint(self):
        provider = WebSearchProvider(endpoint="https://search.example/q={query}")
        items = provider.search(["Codex fantasy"], "u1")
        self.assertEqual(len(items), 1)
        self.assertIn("search.example/q=codex-fantasy", items[0].location)
        self.assertEqual(items[0].discovered_by, "web_search")

    def test_sitemap_provider_probes_children(self):
        xml = (
            b"<?xml version='1.0'?><urlset>"
            b"<url><loc>https://codex.example/a</loc></url>"
            b"<url><loc>https://codex.example/b</loc></url></urlset>"
        )
        client = _Client({"https://codex.example.org/sitemap.xml": (200, xml)})
        items = SitemapProvider(client=client).search(["Codex"], "u1")
        self.assertEqual(
            [i.location for i in items],
            ["https://codex.example/a", "https://codex.example/b"],
        )
        self.assertTrue(all(i.discovered_by == "sitemap" for i in items))

    def test_feed_provider_probes_links(self):
        xml = (
            b"<rss><channel><item>"
            b"<link>https://codex.example/p1</link>"
            b"</item></channel></rss>"
        )
        client = _Client({"https://codex.example.org/feed.xml": (200, xml)})
        items = FeedProvider(client=client).search(["Codex"], "u1")
        self.assertEqual(items[0].location, "https://codex.example/p1")
        self.assertEqual(items[0].discovered_by, "feed")

    def test_discover_dedupes_and_applies_limit(self):
        candidates = [
            Candidate(
                "1", "u1", "website", "https://a.test/x", "A", 0.9, "p",
                score_breakdown={"relevance": 0.9},
            ),
            Candidate(
                "2", "u1", "website", "https://a.test/x/", "A2", 0.8, "p",
                score_breakdown={"relevance": 0.8},
            ),
            Candidate(
                "3", "u1", "website", "https://b.test/x", "B", 0.7, "p",
                score_breakdown={"relevance": 0.7},
            ),
        ]

        class P:
            def search(self, _k, _u, **_kw):
                return candidates

        out = discover(
            self.universe, 0, providers=[P()],
            settings={"discovery_max_candidates": 1},
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].location, "https://a.test/x")

    def test_scoring_adds_breakdown_and_homonym_risk(self):
        class P:
            def search(self, _k, uid, **_kw):
                return [
                    Candidate(
                        "1", uid, "website", "https://other.test/x",
                        "Mercury planet", 0.9, "raw",
                    )
                ]

        out = discover(
            {"id": "u2", "name": "Mercury RPG", "description": ""},
            0, providers=[P()],
        )
        self.assertEqual(len(out), 1)
        self.assertIn("relevance", out[0].score_breakdown)
        self.assertTrue(
            out[0].metadata.get("homonym_risk") or out[0].score <= 0.9
        )

    def test_default_providers_respect_settings(self):
        providers = build_default_providers({
            "discovery_sitemaps": False,
            "discovery_feeds": False,
            "discovery_web_search": False,
            "discovery_git": False,
            "discovery_wiki": False,
        })
        names = [type(p).__name__ for p in providers]
        self.assertEqual(names, ["KeywordProvider"])

    def test_homonym_metadata_reason_present(self):
        class P:
            def search(self, _k, uid, **_kw):
                return [Candidate("1", uid, "website", "https://github.com/x",
                                  "Mercury element", 0.2, "raw",
                                  discovered_by="web_search")]

        out = discover(
            {"id": "u", "name": "Mercury RPG", "description": ""},
            0,
            providers=[P()],
        )
        self.assertTrue(out[0].metadata.get("homonym_risk"))
        self.assertIn("homonym_reason", out[0].metadata)

    def test_sitemap_provider_probes_real_universe_hosts_via_robots(self):
        robots = b"User-agent: *\nSitemap: https://lore.example/custom-sitemap.xml\n"
        xml = (
            b"<urlset><url><loc>https://lore.example/ch1</loc></url></urlset>"
        )
        client = _Client({
            "https://lore.example/robots.txt": (200, robots),
            "https://lore.example/custom-sitemap.xml": (200, xml),
        })
        universe = {
            "id": "u1", "name": "Dune",
            "_discovery_cfg": {"existing_sources": ["https://lore.example/en"]},
        }
        items = SitemapProvider(client=client).search(["Dune"], "u1", universe=universe)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].location, "https://lore.example/custom-sitemap.xml")
        self.assertEqual(items[0].kind, "sitemap")

    def test_wiki_provider_discovers_official_wiki_and_multilingual_wikipedia(self):
        from warframe_lore.v1.scraper.discovery.providers.wiki import WikiProvider

        wiki_ok = b'{"query":{"general":{"mainpage":"Main Page"}}}'
        wp_en = b'{"query":{"search":[{"title":"Dune (franchise)"}]}}'
        wp_fr = b'{"query":{"search":[{"title":"Dune (univers)"}]}}'

        class WikiTestClient:
            def get(self, url: str, **_kw):
                if "dune.wiki.gg/api.php" in url:
                    return _Resp(200, wiki_ok)
                if "en.wikipedia.org/w/api.php" in url:
                    return _Resp(200, wp_en)
                if "fr.wikipedia.org/w/api.php" in url:
                    return _Resp(200, wp_fr)
                return _Resp(404, b"")

        items = WikiProvider().search(["Dune"], "u1", client=WikiTestClient())
        locs = [item.location for item in items]
        self.assertIn("https://dune.wiki.gg/", locs)
        self.assertIn("https://en.wikipedia.org/wiki/Dune_%28franchise%29", locs)
        self.assertIn("https://fr.wikipedia.org/wiki/Dune_%28univers%29", locs)


if __name__ == "__main__":
    unittest.main()
