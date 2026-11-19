"""S0 contract: dossiers are named, unique, isolated and persisted as JSON."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from warframe_lore.v1.scraper.universes import (
    UniverseExistsError,
    UniverseStore,
    new_universe,
)


class NewUniverseTests(unittest.TestCase):
    def test_name_becomes_a_stable_slug(self):
        universe = new_universe("Le Seigneur des Anneaux")
        self.assertEqual(universe.slug, "le-seigneur-des-anneaux")

    def test_explicit_slug_is_kept(self):
        universe = new_universe("Warframe", slug="wframe")
        self.assertEqual(universe.slug, "wframe")

    def test_empty_name_is_rejected(self):
        for name in ("", "   ", "\t\n"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                new_universe(name)

    def test_invalid_slug_is_rejected(self):
        with self.assertRaises(ValueError):
            new_universe("Warframe", slug="Warframe/Universe")

    def test_timestamps_are_filled(self):
        universe = new_universe("Warframe")
        self.assertTrue(universe.created_at)
        self.assertEqual(universe.updated_at, universe.created_at)


class UniverseStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = UniverseStore(Path(self.tmp.name) / "v1")

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_and_list(self):
        self.store.create("Warframe")
        self.store.create("Elden Ring")
        self.assertEqual(
            [universe.name for universe in self.store.list()],
            ["Elden Ring", "Warframe"],
        )

    def test_duplicate_slug_is_rejected(self):
        self.store.create("Warframe")
        with self.assertRaises(UniverseExistsError):
            self.store.create("Warframe")

    def test_universe_is_written_to_its_own_directory(self):
        universe = self.store.create(
            "Warframe", description="Un univers de science-fiction")
        path = self.store.root / universe.slug / "universe.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["name"], "Warframe")
        self.assertEqual(payload["description"], "Un univers de science-fiction")

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.store.get("absent"))

    def test_delete_removes_the_directory(self):
        universe = self.store.create("Warframe")
        self.assertTrue(self.store.delete(universe.slug))
        self.assertFalse(self.store.delete(universe.slug))
        self.assertEqual(self.store.list(), [])


if __name__ == "__main__":
    unittest.main()
