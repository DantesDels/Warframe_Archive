"""Native UI contract: workspace state and desktop window behavior."""

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
from warframe_lore.v1.scraper.UI import AtelierApp, WorkshopWorkspace, empty_data
from warframe_lore.v1.scraper.UI.dialogs.preflight_dialog import PreflightDialog
from warframe_lore.v1.scraper.UI.dialogs.settings_dialog import SettingsDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _seed_workspace() -> WorkshopWorkspace:
    ws = WorkshopWorkspace(data=empty_data())
    ws.create("Warframe", "Univers de science-fiction")
    ws.create("Droit constitutionnel", "Sources juridiques")
    ws.add_manual_source(
        "warframe", "https://warframe.fandom.com/wiki/Lore", kind="website"
    )
    ws.add_manual_source(
        "droit-constitutionnel", "https://example.org/constitution", kind="website"
    )
    return ws


class WorkspaceDataTests(unittest.TestCase):
    def test_empty_data_has_expected_keys(self):
        self.assertEqual(
            set(empty_data()),
            {"candidates", "universes", "sources", "documents", "runs"},
        )

    def test_workspace_persists_to_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace.json"
            ws = WorkshopWorkspace(path=path)
            ws.create("Warframe")
            ws.add_manual_source("warframe", "https://example.org", kind="website")
            loaded = WorkshopWorkspace(path=path)
            self.assertEqual(len(loaded.universes()), 1)
            self.assertEqual(len(loaded.sources_for("warframe")), 1)


class UniverseWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.workspace = _seed_workspace()

    def test_create_adds_universes_with_unique_ids(self):
        first = self.workspace.create("Nouvel Univers")
        second = self.workspace.create("Nouvel Univers")
        self.assertEqual(first["id"], "nouvel-univers")
        self.assertEqual(second["id"], "nouvel-univers-2")

    def test_create_rejects_blank_name(self):
        with self.assertRaises(ValueError):
            self.workspace.create("   ")

    def test_rename_keeps_identity_and_updates_label(self):
        universe = self.workspace.rename("warframe", "  Warframe Prime  ")
        self.assertEqual(universe["id"], "warframe")
        self.assertEqual(universe["name"], "Warframe Prime")

    def test_rename_rejects_duplicate_name(self):
        with self.assertRaises(ValueError):
            self.workspace.rename("warframe", "Droit constitutionnel")

    def test_details_are_scoped_to_selected_universe(self):
        self.assertEqual(len(self.workspace.sources_for("warframe")), 1)
        self.assertEqual(len(self.workspace.sources_for("droit-constitutionnel")), 1)


class DesktopWindowTests(unittest.TestCase):
    def setUp(self):
        _app()
        self.tmp = tempfile.TemporaryDirectory()
        self.data_path = Path(self.tmp.name) / "workspace.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _make_app(self) -> AtelierApp:
        ws = _seed_workspace()
        ws.path = self.data_path
        return AtelierApp(workspace=ws, data_path=self.data_path)

    def test_details_only_after_selection(self):
        app = self._make_app()
        self.assertIsNone(app.selected_id())
        self.assertEqual(app.details.title.text(), "Aucun Univers sélectionné")
        app.sidebar.select("warframe")
        self.assertEqual(app.selected_id(), "warframe")
        self.assertEqual(app.details.title.text(), "Warframe")
        tabs = app.details.findChild(QTabWidget)
        self.assertIsNotNone(tabs)
        self.assertEqual(tabs.count(), 5)
        app.sidebar.select(None)
        app.on_select(None)
        self.assertEqual(app.details.title.text(), "Aucun Univers sélectionné")
        app.close()
        app.deleteLater()

    def test_header_badge_and_ready_status(self):
        app = self._make_app()
        count = len(app.workspace.universes())
        self.assertIn(f"{count} Univers", app.header.meta.text())
        self.assertEqual(app.status_bar.currentMessage(), "Statut : Prêt")
        app.close()
        app.deleteLater()

    def test_sidebar_actions_icon_only_with_tooltips(self):
        app = self._make_app()
        all_btns = [
            b for b in app.sidebar.findChildren(QPushButton)
            if b.objectName() == "SidebarIconButton"
        ]
        sidebar_tips = {
            "Renommer (F2)", "Param\u00e8tres globaux",
            "Synchroniser tout", "Nouvel Univers",
        }
        buttons = [
            b for b in all_btns
            if b.toolTip() in sidebar_tips and not app.sidebar.list.isAncestorOf(b)
        ]
        self.assertEqual(len(buttons), 4)
        self.assertEqual({b.toolTip() for b in buttons}, sidebar_tips)
        app.close()
        app.deleteLater()

    def test_universe_tile_actions_visible_only_when_selected(self):
        app = self._make_app()
        app.sidebar.select("warframe")
        QApplication.processEvents()
        selected = None
        for i in range(app.sidebar.list.count()):
            item = app.sidebar.list.item(i)
            if item.data(0x0100) == "warframe":
                selected = app.sidebar.list.itemWidget(item)
        self.assertIsNotNone(selected)
        self.assertFalse(selected.actions.isHidden())
        tips = {
            b.toolTip() for b in selected.actions.findChildren(QPushButton)
            if b.objectName() == "SidebarIconButton"
        }
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
            fmt = [cb.text() for cb in dialog.findChildren(QCheckBox)]
            self.assertIn("Limiter au mÃªme domaine", fmt)
            self.assertIn("Cache HTTP conditionnel", fmt)
            self.assertIn("IncrÃ©mental (ignorer contenu inchangÃ©)", fmt)
            self.assertIn("DÃ©velopper les index/manifests", fmt)
            expected = ["JSON", "JSONL", "CSV", "Markdown", "SQL", "NoSQL"]
            got = [f for f in fmt if f in set(expected)]
            self.assertEqual(got, expected)
            dialog.deleteLater()

    def test_preflight_dialog_french_buttons_and_formats(self):
        dialog = PreflightDialog(None, Settings(), ("warframe",), 3)
        box = dialog.findChild(QDialogButtonBox)
        texts = [btn.text() for btn in box.buttons()]
        self.assertIn("Lancer", texts)
        self.assertIn("Annuler", texts)
        fmt = [cb.text() for cb in dialog.findChildren(QCheckBox)]
        self.assertIn("Limiter au mÃªme domaine", fmt)
        self.assertIn("Cache HTTP conditionnel", fmt)
        self.assertIn("IncrÃ©mental (ignorer contenu inchangÃ©)", fmt)
        self.assertIn("DÃ©velopper les index/manifests", fmt)
        expected = ["JSON", "JSONL", "CSV", "Markdown", "SQL", "NoSQL"]
        got = [f for f in fmt if f in set(expected)]
        self.assertEqual(got, expected)
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
