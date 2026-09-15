"""Site source tests: route discovery, delta, fetch, catalogue multi-source.

All tests run offline through fakes (no network, no real HTTP).
"""

from __future__ import annotations

import unittest

from warframe_lore.api import CategoryCatalog, CategorySpec, SiteHtmlSource
from warframe_lore.api.buckets import DEFAULT_BUCKETS
from warframe_lore.api.buckets.config import BucketConfig
from warframe_lore.api.models import TouchedInfo
from warframe_lore.api.site_crawl import crawl_paths, extract_fr_paths
from warframe_lore.config import Config


class ExtractFrPathsTests(unittest.TestCase):
    """href -> normalized /fr path filtering."""

    def test_keeps_internal_and_drops_noise(self):
        html = (
            '<a href="https://www.warframe.com/fr/news/a">a</a>'
            '<a href="/fr/game/warframes">b</a>'
            '<a href="https://forums.warframe.com/fr/oops">c</a>'
            '<a href="#fragment">d</a>'
            '<a href="https://www.warframe.com/fr/guides/quests?tab=1">e</a>'
            '<a href="https://www-static.warframe.com/foo.css">f</a>'
            '<a href="javascript:void(0)">g</a>'
            '<a href="//www.warframe.com/fr/mirror">h</a>'
        )
        paths = extract_fr_paths(html, "/fr", "www.warframe.com")
        self.assertEqual(
            paths,
            {"/fr/news/a", "/fr/game/warframes", "/fr/guides/quests"},
        )


class CrawlPathsTests(unittest.TestCase):
    """BFS walk with a fake get_text (no network)."""

    def setUp(self):
        self.pages = {
            "/fr": "<a href='/fr/news'>1</a> <a href='/fr/shop'>2</a>",
            "/fr/news": "<a href='/fr/news/welcome'>3</a>",
            "/fr/news/welcome": "",
        }

    def test_walk_and_exclude_transactional(self):
        seen = crawl_paths(
            self.pages.get, "/fr", prefix="/fr", host="www.warframe.com",
            exclude=("/shop",), max_pages=100)
        self.assertEqual(seen, {"/fr", "/fr/news", "/fr/news/welcome"})

    def test_max_pages_caps_the_walk(self):
        seen = crawl_paths(
            self.pages.get, "/fr", prefix="/fr", host="www.warframe.com",
            exclude=(), max_pages=2)
        self.assertEqual(len(seen), 2)
        self.assertIn("/fr", seen)


class _FakeResp:
    """Minimal ``requests.Response`` stand-in carrying headers."""

    def __init__(self, headers=None) -> None:
        self.headers = headers or {}


class _FakeHttp:
    """In-memory stand-in for ``SiteHttp``."""

    def __init__(self, pages) -> None:
        self.pages = pages

    def get_text(self, path):
        return self.pages.get(path)

    def fetch(self, path):
        html = self.pages.get(path)
        return None if html is None else (html, f'"{path}"')

    def head(self, path):
        return (_FakeResp({"ETag": f'"{path}"'})
                if path in self.pages else None)


class SiteHtmlSourceTests(unittest.TestCase):
    """resolved catalogue, light delta and page fetching."""

    def setUp(self):
        self.pages = {
            "/fr": "<a href='/fr/news/welcome'>x</a>",
            "/fr/news/welcome": "<h1>Bienvenue</h1>",
        }
        self.source = SiteHtmlSource(Config())
        self.source.http = _FakeHttp(self.pages)

    def test_resolve_categories_crawls_the_seed(self):
        resolved = self.source.resolve_categories(["/fr", "/fr/news/welcome"])
        self.assertEqual(
            resolved["/fr"], {"/fr", "/fr/news/welcome"})
        self.assertEqual(resolved["/fr/news/welcome"], {"/fr/news/welcome"})

    def test_check_updates_returns_etag_signal_and_missing(self):
        info = self.source.check_updates(["/fr", "/fr/missing"])
        self.assertEqual(info["/fr"], TouchedInfo(None, "/fr", touched='"/fr"'))
        self.assertTrue(info["/fr/missing"].missing)
        self.assertFalse(info["/fr"].missing)

    def test_check_updates_keeps_page_when_no_freshness_header(self):
        self.source.http = _FakeHttp(self.pages)
        self.source.http.head = lambda path: _FakeResp({})
        info = self.source.check_updates(["/fr"])["/fr"]
        self.assertFalse(info.missing)
        self.assertIsNone(info.touched)

    def test_fetch_pages_returns_html_url_and_touched(self):
        page = self.source.fetch_pages(["/fr/news/welcome", "/fr/nope"])[
            "/fr/news/welcome"]
        self.assertEqual(page.title, "/fr/news/welcome")
        self.assertEqual(page.url, "https://www.warframe.com/fr/news/welcome")
        self.assertIn("<h1>Bienvenue</h1>", page.content)
        self.assertEqual(page.touched, '"/fr/news/welcome"')
        self.assertNotIn("/fr/nope", self.pages)


class MultiSourceCatalogTests(unittest.TestCase):
    """One source per bucket (`CategorySpec.source`)."""

    def setUp(self):
        class SourceA:
            name = "src_a"

            def resolve_categories(self, names):
                return {name: {f"a-{name}"} for name in names}

            def resolve_prefix(self, prefix):
                return set()

        class SourceB:
            name = "src_b"

            def resolve_categories(self, names):
                return {name: {f"b-{name}"} for name in names}

            def resolve_prefix(self, prefix):
                return set()

        self.catalog = CategoryCatalog({"src_a": SourceA(), "src_b": SourceB()})

    def test_resolve_uses_the_bucket_source(self):
        spec_a = CategorySpec(
            id="x", title="x", filename="x", source="src_a",
            categories=["seed"])
        spec_b = CategorySpec(
            id="y", title="y", filename="y", source="src_b",
            categories=["seed"])
        self.assertEqual(self.catalog.resolve(spec_a).page_titles, {"a-seed"})
        self.assertEqual(self.catalog.resolve(spec_b).page_titles, {"b-seed"})


class SiteBucketConfigTests(unittest.TestCase):
    """The official-site bucket ships in defaults and buckets.json."""

    def test_site_bucket_in_defaults(self):
        spec = next(s for s in DEFAULT_BUCKETS
                    if s.id == "Lore_Site_Officiel_FR")
        self.assertEqual(spec.source, "warframe-com-fr")
        self.assertEqual(spec.filename, "Lore_Site_Officiel_FR.json")
        self.assertEqual(spec.categories, ["/fr"])
        self.assertIn("/shop", spec.title_exclude)

    def test_site_bucket_loads_from_bucket_config(self):
        specs = BucketConfig().specs
        self.assertIn(
            "Lore_Site_Officiel_FR", [s.id for s in specs])


if __name__ == "__main__":
    unittest.main()
