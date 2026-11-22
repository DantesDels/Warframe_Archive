"""Native UI contract: mock data, universe state and desktop window behavior."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialogButtonBox,
    QPushButton,
    QTabWidget,
)

from warframe_lore.v1.scraper.settings import Settings, SettingsStore
from warframe_lore.v1.scraper.UI import MOCK_DATA, AtelierApp, WorkshopWorkspace
from warframe_lore.v1.scraper.UI.dialogs.preflight_dialog import PreflightDialog
from warframe_lore.v1.scraper.UI.dialogs.settings_dialog import SettingsDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


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
        self.workspace.rename("warframe", "Renomm?")
        self.assertEqual(MOCK_DATA["universes"][0]["name"], "Warframe")


class DesktopWindowTests(unittest.TestCase):
    def setUp(self):
        _app()

    def test_details_only_after_selection(self):
        app = AtelierApp()
        self.assertIsNone(app.selected_id())
        self.assertEqual(app.details.title.text(), "Aucun Univers sélectionné")
        app.sidebar.select("warframe")
        self.assertEqual(app.selected_id(), "warframe")
        self.assertEqual(app.details.title.text(), "Warframe")
        tabs = app.details.findChild(QTabWidget)
        self.assertIsNotNone(tabs)
        self.assertEqual(tabs.count(), 4)
        app.sidebar.select(None)
        app.on_select(None)
        self.assertEqual(app.details.title.text(), "Aucun Univers sélectionné")
        app.close()
        app.deleteLater()

    def test_header_badge_and_no_duplicate_ready_status(self):
        app = AtelierApp()
        count = len(app.workspace.universes())
        self.assertNotIn("Universs", app.header.meta.text())
        self.assertIn(f"{count} Univers", app.header.meta.text())
        self.assertEqual(app.status_bar.currentMessage(), "Statut : Prêt")
        self.assertNotEqual(app.execution.step_label.text(), "Statut : Prêt")
        app.close()
        app.deleteLater()

    def test_sidebar_actions_are_icon_only_with_tooltips(self):
        app = AtelierApp()
        all_btns = [
            btn for btn in app.sidebar.findChildren(QPushButton)
            if btn.objectName() == "SidebarIconButton"
        ]
        sidebar_tips = {
            "Renommer (F2)",
            "Param\u00e8tres globaux",
            "Synchroniser tout",
            "Nouvel Univers",
        }
        buttons = [
            b for b in all_btns
            if b.toolTip() in sidebar_tips and not app.sidebar.list.isAncestorOf(b)
        ]
        self.assertEqual(len(buttons), 4)
        self.assertEqual({b.toolTip() for b in buttons}, sidebar_tips)
        self.assertTrue(all(b.text().strip() for b in buttons))
        self.assertTrue(all(len(b.text()) <= 2 for b in buttons))
        create = [b for b in buttons if b.toolTip() == "Nouvel Univers"][0]
        self.assertIs(create.parent(), app.sidebar)
        layout = app.sidebar.layout()
        bottom_row = layout.itemAt(layout.count() - 1).layout()
        self.assertIs(bottom_row.itemAt(bottom_row.count() - 1).widget(), create)
        app.close()
        app.deleteLater()

    def test_universe_tile_actions_visible_only_when_selected(self):
        app = AtelierApp()
        app.sidebar.select("warframe")
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        selected = None
        for i in range(app.sidebar.list.count()):
            item = app.sidebar.list.item(i)
            if item.data(0x0100) == "warframe":
                selected = app.sidebar.list.itemWidget(item)
        self.assertIsNotNone(selected)
        self.assertFalse(selected.actions.isHidden())
        buttons = [
            b for b in selected.actions.findChildren(QPushButton)
            if b.objectName() == "SidebarIconButton"
        ]
        tips = {b.toolTip() for b in buttons}
        self.assertEqual(tips, {"Exécuter", "Synchroniser l'Univers", "Supprimer"})
        app.sidebar.select(None)
        app.on_select(None)
        QApplication.processEvents()
        for i in range(app.sidebar.list.count()):
            widget = app.sidebar.list.itemWidget(app.sidebar.list.item(i))
            self.assertFalse(widget.actions.isVisible())
        app.close()
        app.deleteLater()

    def test_settings_dialog_french_buttons_and_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp) / "settings.json")
            dialog = SettingsDialog(None, store)
            box = dialog.findChild(QDialogButtonBox)
            texts = [btn.text() for btn in box.buttons()]
            self.assertIn("Enregistrer", texts)
            self.assertIn("Annuler", texts)
            fmt = [cb.text() for cb in dialog.findChildren(QCheckBox)[:6]]
            self.assertEqual(fmt, ["JSON", "JSONL", "CSV", "Markdown", "SQL", "NoSQL"])
            dialog.deleteLater()

    def test_preflight_dialog_french_buttons_and_formats(self):
        dialog = PreflightDialog(None, Settings(), ("warframe",), 3)
        box = dialog.findChild(QDialogButtonBox)
        texts = [btn.text() for btn in box.buttons()]
        self.assertIn("Lancer", texts)
        self.assertIn("Annuler", texts)
        fmt = [cb.text() for cb in dialog.findChildren(QCheckBox)[:6]]
        self.assertEqual(fmt, ["JSON", "JSONL", "CSV", "Markdown", "SQL", "NoSQL"])
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
