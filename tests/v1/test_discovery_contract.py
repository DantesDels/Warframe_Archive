"""Keyword discovery contract."""

from __future__ import annotations

import unittest

from warframe_lore.v1.scraper.discovery import (
    KeywordProvider,
    discover,
    keywords_for,
)


class KeywordsTests(unittest.TestCase):
    def test_extracts_unique_keywords(self):
        result = keywords_for("Codex", "Codex de fantasy ; grimoires")
        self.assertEqual(result[:2], ["Codex", "fantasy"])

    def test_short_words_are_ignored(self):
        self.assertEqual(keywords_for("A et B"), [])


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.universe = {"id": "u1", "name": "Codex", "description": ""}

    def test_provider_uses_generic_templates(self):
        candidates = KeywordProvider().search(["Codex"], "u1")
        self.assertEqual(len(candidates), 4)
        self.assertEqual({item.kind for item in candidates},
                         {"website", "api", "document"})

    def test_threshold_filters_candidates(self):
        low = discover(self.universe, 0)
        high = discover(self.universe, 99)
        self.assertTrue(low)
        self.assertTrue(all(item.score * 100 >= 99 for item in high))
        self.assertLess(len(high), len(low))

    def test_discovery_is_deterministic(self):
        universe = {"id": "u2", "name": "Droit constitutionnel", "description": ""}
        self.assertEqual(discover(universe, 50), discover(universe, 50))

    def test_no_domain_hardcoding(self):
        universe = {"id": "u3", "name": "Warhammer 40k", "description": ""}
        candidates = discover(universe, 0)
        self.assertTrue(any("warhammer" in item.location.lower()
                            for item in candidates))
        self.assertTrue(all("warframe" not in item.location.lower()
                            for item in candidates))


if __name__ == "__main__":
    unittest.main()
