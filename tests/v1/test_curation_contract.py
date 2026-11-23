"""Curation state contract."""

from __future__ import annotations

import unittest

from warframe_lore.v1.scraper.discovery import Candidate, discover
from warframe_lore.v1.scraper.UI import WorkshopWorkspace


class CurationTests(unittest.TestCase):
    def setUp(self):
        self.workspace = WorkshopWorkspace()
        self.workspace.create("Warframe")
        self.workspace.create("Droit constitutionnel")

    def test_candidates_are_scoped_and_serialized(self):
        universe = self.workspace.get("warframe")
        assert universe is not None
        candidates = discover(universe, 60)
        self.workspace.set_candidates(candidates)
        self.assertEqual(
            len(self.workspace.candidates_for("warframe")),
            len(candidates),
        )
        self.assertEqual(self.workspace.candidates_for("droit-constitutionnel"), [])

    def test_activation_adds_a_source(self):
        self.workspace.set_candidates([
            Candidate(
                id="cand-1",
                universe_id="warframe",
                kind="website",
                location="https://example.org/docs",
                title="Documentation",
                score=0.9,
                proof="Mot-clé",
            ),
        ])
        before = len(self.workspace.sources_for("warframe"))
        self.workspace.add_source_from_candidate("cand-1")
        self.assertEqual(len(self.workspace.sources_for("warframe")), before + 1)
        self.assertEqual(self.workspace._candidate("cand-1")["status"], "active")

    def test_manual_source_and_deletion(self):
        source = self.workspace.add_manual_source(
            "droit-constitutionnel", "https://example.org/loi",
        )
        self.assertEqual(source["discoveredBy"], "manuel")
        self.workspace.delete_source(source["id"])
        remaining = self.workspace.sources_for("droit-constitutionnel")
        self.assertNotIn(source["id"], {item["id"] for item in remaining})

    def test_delete_universe_cascades(self):
        self.workspace.delete_universe("warframe")
        self.assertIsNone(self.workspace.get("warframe"))
        self.assertEqual(self.workspace.sources_for("warframe"), [])
        self.assertEqual(self.workspace.documents_for("warframe"), [])
        self.assertEqual(self.workspace.runs_for("warframe"), [])


if __name__ == "__main__":
    unittest.main()
