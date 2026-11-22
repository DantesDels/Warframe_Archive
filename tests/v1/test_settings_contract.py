"""Settings validation and persistence contract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from warframe_lore.v1.scraper.settings import (
    OUTPUT_FORMATS,
    LaunchPlan,
    Settings,
    SettingsStore,
)


class SettingsTests(unittest.TestCase):
    def test_defaults_are_valid(self):
        settings = Settings()
        self.assertEqual(settings.min_relevance, 60)
        self.assertEqual(settings.output_formats, ("json", "markdown"))
        self.assertTrue(settings.rag_coupling)
        self.assertEqual(settings.max_pages_per_source, 25)
        self.assertEqual(settings.max_depth, 1)
        self.assertTrue(settings.same_host_only)
        self.assertTrue(settings.use_cache)
        self.assertTrue(settings.incremental)
        self.assertTrue(settings.expand_manifests)
        self.assertEqual(settings.max_manifest_urls, 50)

    def test_rejects_invalid_threshold(self):
        for value in (-1, 101):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Settings(min_relevance=value)

    def test_rejects_unknown_and_empty_formats(self):
        with self.assertRaises(ValueError):
            Settings(output_formats=())
        with self.assertRaises(ValueError):
            Settings(output_formats=("xml",))
        expected = {"json", "jsonl", "csv", "markdown", "sql", "nosql"}
        self.assertTrue(expected <= set(OUTPUT_FORMATS))


class LaunchPlanTests(unittest.TestCase):
    def test_requires_at_least_one_universe(self):
        with self.assertRaises(ValueError):
            LaunchPlan(Settings(), ())


class SettingsStoreTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "nested" / "settings.json")
            self.assertEqual(store.load(), Settings())
            settings = Settings(75, ("jsonl", "csv"), False)
            store.save(settings)
            self.assertEqual(store.load(), settings)


if __name__ == "__main__":
    unittest.main()
