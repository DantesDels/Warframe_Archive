"""Native UI contract: mock data, universe state and desktop window behavior."""

from __future__ import annotations

import unittest

from warframe_lore.v1.scraper.UI import MOCK_DATA, AtelierApp, WorkshopWorkspace


class MockDataTests(unittest.TestCase):
    def test_collections_use_universe_keys(self):
        self.assertEqual(
            set(MOCK_DATA),
            {"candidates", "universes", "sources", "documents", "runs"},
        )
        self.assertTrue(all("universeId" in item for item in MOCK_DATA["sources"]))
        self.assertTrue(all("universeId" in item for item in MOCK_DATA["documents"]))
        self.assertTrue(all("universeIds" in item for item in MOCK_DATA["runs"]))

    def test_mock_references_are_consistent(self):
        universe_ids = {item["id"] for item in MOCK_DATA["universes"]}
        source_ids = {item["id"] for item in MOCK_DATA["sources"]}
        for source in MOCK_DATA["sources"]:
            self.assertIn(source["universeId"], universe_ids)
        for document in MOCK_DATA["documents"]:
            self.assertIn(document["universeId"], universe_ids)
            self.assertIn(document["sourceId"], source_ids)
        for run in MOCK_DATA["runs"]:
            self.assertTrue(run["universeIds"])
            self.assertTrue(set(run["universeIds"]) <= universe_ids)


class UniverseWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.workspace = WorkshopWorkspace()

    def test_create_adds_universes_with_unique_ids(self):
        first = self.workspace.create("Nouvel Univers")
        second = self.workspace.create("Nouvel Univers")
        self.assertEqual(first["id"], "nouvel-univers")
        self.assertEqual(second["id"], "nouvel-univers-2")
        self.assertEqual(len(self.workspace.universes()), 5)

    def test_create_rejects_blank_name(self):
        with self.assertRaises(ValueError):
            self.workspace.create("   ")

    def test_rename_keeps_identity_and_updates_label(self):
        universe = self.workspace.rename("warframe", "  Warframe Prime  ")
        self.assertEqual(universe["id"], "warframe")
        self.assertEqual(universe["name"], "Warframe Prime")
        self.assertEqual(universe["slug"], "warframe-prime")
        self.assertIs(self.workspace.get("warframe"), universe)

    def test_rename_rejects_duplicate_name(self):
        with self.assertRaises(ValueError):
            self.workspace.rename("warframe", "Droit constitutionnel")

    def test_details_are_scoped_to_selected_universe(self):
        self.assertEqual(len(self.workspace.sources_for("warframe")), 3)
        self.assertEqual(
            len(self.workspace.documents_for("droit-constitutionnel")),
            2,
        )
        self.assertEqual(
            {run["id"] for run in self.workspace.runs_for("warframe")},
            {"run-wf-1", "run-multi-1"},
        )

    def test_workspace_does_not_mutate_mock_data(self):
        self.workspace.rename("warframe", "Renommé")
        self.assertEqual(MOCK_DATA["universes"][0]["name"], "Warframe")


class DesktopWindowTests(unittest.TestCase):
    def test_details_only_after_selection(self):
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest("tkinter unavailable")
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("no graphical display available")
        root.withdraw()
        try:
            app = AtelierApp(root)
            self.assertIsNone(app.tree.selected_id())
            self.assertEqual(
                app.details.title_label.cget("text"),
                "Aucun Univers sélectionné",
            )
            app.tree.select("warframe")
            app.on_select("warframe")
            self.assertEqual(app.details.title_label.cget("text"), "Warframe")
            notebook = app.details.body.winfo_children()[0]
            self.assertEqual(notebook.index("end"), 4)
            app.on_select(None)
            self.assertEqual(
                app.details.title_label.cget("text"),
                "Aucun Univers sélectionné",
            )
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
