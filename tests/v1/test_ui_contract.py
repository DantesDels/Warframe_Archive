"""Native UI contract: workspace state and desktop window behavior."""

from __future__ import annotations

import os
import tempfile
import unittest
from itertools import combinations
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialogButtonBox,
    QPushButton,
    QStyleOptionGraphicsItem,
    QTabWidget,
)

from warframe_lore.v1.scraper.settings import Settings, SettingsStore
from warframe_lore.v1.scraper.UI import AtelierApp, WorkshopWorkspace, empty_data
from warframe_lore.v1.scraper.UI.dialogs.preflight_dialog import PreflightDialog
from warframe_lore.v1.scraper.UI.dialogs.settings_dialog import SettingsDialog
from warframe_lore.v1.scraper.UI.graph.items import (
    LABEL_BACKGROUND,
    LABEL_COLOR,
    GraphNodeItem,
    node_tooltip,
)
from warframe_lore.v1.scraper.UI.graph.layout import (
    CELL_HEIGHT,
    CELL_WIDTH,
    layout_positions,
    short_label,
)
from warframe_lore.v1.scraper.UI.graph.view import GraphCanvas
from warframe_lore.v1.scraper.UI.style import app_stylesheet
from warframe_lore.v1.scraper.UI.views.simple_table import SimpleTable
from warframe_lore.v1.scraper.UI.views.tabs_candidates import candidates_view

UI_ROOT = (
    Path(__file__).resolve().parents[2] / "warframe_lore" / "v1" / "scraper" / "UI"
)
MOJIBAKE_TOKENS = (
    "\u00c3\u00a9",
    "\u00c3\u00aa",
    "\u00c3\u00a8",
    "\u00c3\u00a0",
    "\u00e2\u0080\u0099",
    "\u00c2\u00a0",
)


def _app() -> QApplication:
    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


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
            {
                "candidates", "universes", "sources", "documents",
                "document_versions", "runs", "capabilities",
            },
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
        assert tabs is not None
        self.assertEqual(tabs.count(), 6)
        self.assertEqual(tabs.tabText(5), "Graphe")
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
        from warframe_lore.v1.scraper.UI.views.sidebar_item import UniverseItem

        selected: UniverseItem | None = None
        for i in range(app.sidebar.list.count()):
            item = app.sidebar.list.item(i)
            if item.data(0x0100) == "warframe":
                widget = app.sidebar.list.itemWidget(item)
                if isinstance(widget, UniverseItem):
                    selected = widget
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertFalse(selected.actions_widget.isHidden())
        tips = {
            b.toolTip() for b in selected.actions_widget.findChildren(QPushButton)
            if b.objectName() == "SidebarIconButton"
        }
        self.assertEqual(tips, {"Exécuter", "Synchroniser l'Univers", "Supprimer"})
        app.sidebar.select(None)
        app.on_select(None)
        QApplication.processEvents()
        for i in range(app.sidebar.list.count()):
            widget = app.sidebar.list.itemWidget(app.sidebar.list.item(i))
            assert isinstance(widget, UniverseItem)
            self.assertFalse(widget.actions_widget.isVisible())
        app.close()
        app.deleteLater()

    def test_settings_dialog_french_buttons_and_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp) / "settings.json")
            dialog = SettingsDialog(None, store)
            box = dialog.findChild(QDialogButtonBox)
            self.assertIsNotNone(box)
            assert box is not None
            texts = [btn.text() for btn in box.buttons()]
            self.assertIn("Enregistrer", texts)
            self.assertIn("Annuler", texts)
            fmt = [cb.text() for cb in dialog.findChildren(QCheckBox)]
            self.assertTrue(dialog.same_host is not None)
            self.assertTrue(any("Cache HTTP" in t for t in fmt))
            self.assertTrue(any("contenu" in t for t in fmt))
            self.assertTrue(any("index/manifests" in t for t in fmt))
            expected = ["JSON", "JSONL", "CSV", "Markdown", "SQL", "NoSQL"]
            got = [f for f in fmt if f in set(expected)]
            self.assertEqual(got, expected)
            dialog.deleteLater()

    def test_preflight_dialog_french_buttons_and_formats(self):
        dialog = PreflightDialog(None, Settings(), ("warframe",), 3)
        box = dialog.findChild(QDialogButtonBox)
        self.assertIsNotNone(box)
        assert box is not None
        texts = [btn.text() for btn in box.buttons()]
        self.assertIn("Lancer", texts)
        self.assertIn("Annuler", texts)
        fmt = [cb.text() for cb in dialog.findChildren(QCheckBox)]
        self.assertIn("Limiter au même domaine", fmt)
        self.assertIn("Cache HTTP conditionnel", fmt)
        self.assertIn("Incrémental (ignorer contenu inchangé)", fmt)
        self.assertIn("Développer les index/manifests", fmt)
        expected = ["JSON", "JSONL", "CSV", "Markdown", "SQL", "NoSQL"]
        got = [f for f in fmt if f in set(expected)]
        self.assertEqual(got, expected)
        dialog.deleteLater()

    def test_preflight_preserves_advanced_settings(self):
        base = Settings(
            graph_api_enabled=True,
            graph_api_port=9999,
            discovery_git_token="token",
        )
        dialog = PreflightDialog(None, base, ("warframe",), 3)
        dialog._launch()
        self.assertIsNotNone(dialog.selected_plan)
        assert dialog.selected_plan is not None
        settings = dialog.selected_plan.settings
        self.assertTrue(settings.graph_api_enabled)
        self.assertEqual(settings.graph_api_port, 9999)
        self.assertEqual(settings.discovery_git_token, "token")
        dialog.deleteLater()


class UiEncodingContractTests(unittest.TestCase):
    def test_ui_sources_have_no_double_encoded_utf8(self):
        offenders: list[str] = []
        for path in sorted(UI_ROOT.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for token in MOJIBAKE_TOKENS:
                if token in text:
                    offenders.append(f"{path.name}:{ascii(token)}")
        self.assertEqual(offenders, [])

    def test_progress_and_checkbox_contrast_rules(self):
        stylesheet = app_stylesheet()
        self.assertIn("QProgressBar { background: #334155; color: #ffffff;", stylesheet)
        self.assertIn("font-weight: 700; text-align: center;", stylesheet)
        self.assertIn("QProgressBar::chunk { background: #1d4ed8;", stylesheet)
        self.assertIn(
            "QCheckBox::indicator:unchecked { background: #ffffff;", stylesheet
        )
        self.assertIn("border: 1px solid #64748b;", stylesheet)


class GraphRenderingContractTests(unittest.TestCase):
    def test_long_url_labels_are_elided_and_tooltips_keep_details(self):
        url = "https://warframe.fandom.com/wiki/Lore/very/long/document/name"
        node = {
            "id": "Candidate:1",
            "kind": "Candidate",
            "label": url,
            "attrs": {"status": "approved", "score": 0.82},
        }
        label = short_label(node)
        self.assertLessEqual(len(label), 22)
        self.assertTrue(label.endswith("..."))
        tooltip = node_tooltip(node)
        self.assertIn(url, tooltip)
        self.assertIn("Statut : approved", tooltip)
        self.assertIn("Pertinence : 0.82", tooltip)
        _app()
        item = GraphNodeItem(node, (0.0, 0.0))
        self.assertEqual(item.toolTip(), tooltip)

    def test_graph_label_is_light_on_a_dark_pill(self):
        self.assertIn(LABEL_COLOR, ("#f1f5f9", "#ffffff"))
        self.assertEqual(LABEL_BACKGROUND, "#0f172a")
        _app()
        node = {
            "id": "Document:1",
            "kind": "Document",
            "label": "Lore/Archives",
            "attrs": {},
        }
        item = GraphNodeItem(node, (0.0, 0.0))
        image = QImage(240, 100, QImage.Format.Format_ARGB32)
        image.fill(QColor("#1e293b"))
        painter = QPainter(image)
        painter.translate(120, 35)
        item.paint(painter, QStyleOptionGraphicsItem(), None)
        painter.end()
        light_pixels = sum(
            1
            for y in range(46, 74)
            for x in range(60, 180)
            if QColor(image.pixel(x, y)).lightness() >= 200
        )
        self.assertGreater(light_pixels, 50)

    def test_layered_positions_never_overlap(self):
        nodes = [
            {
                "id": "Universe:warframe",
                "kind": "Universe",
                "label": "Warframe",
                "attrs": {},
            }
        ]
        nodes.extend(
            {
                "id": f"Source:{index}",
                "kind": "Source",
                "label": f"https://example.org/source-{index}",
                "attrs": {},
            }
            for index in range(5)
        )
        edges = [
            {
                "source": "Universe:warframe",
                "target": f"Source:{index}",
                "type": "HAS_SOURCE",
            }
            for index in range(5)
        ]
        positions = layout_positions({"nodes": nodes, "edges": edges})
        self.assertEqual(len(positions), len(nodes))
        for first, second in combinations(positions.values(), 2):
            self.assertTrue(
                abs(first[0] - second[0]) >= CELL_WIDTH
                or abs(first[1] - second[1]) >= CELL_HEIGHT
            )

    def test_graph_tab_uses_zoomable_canvas_and_inspector(self):
        _app()
        canvas = GraphCanvas({"nodes": [], "edges": []})
        self.assertIsNotNone(canvas.findChild(QPushButton, "GraphFitButton"))
        self.assertEqual(canvas.detail.objectName(), "GraphNodeDetail")
        with tempfile.TemporaryDirectory() as tmp:
            ws = _seed_workspace()
            ws.path = Path(tmp) / "workspace.json"
            app = AtelierApp(workspace=ws, data_path=ws.path)
            app.sidebar.select("warframe")
            self.assertIsNotNone(app.details.findChild(GraphCanvas))
            app.close()
            app.deleteLater()


class CandidatesTableContractTests(unittest.TestCase):
    def test_location_first_column_is_visible_elided_and_localized(self) -> None:
        _app()
        workspace = _seed_workspace()
        location = "https://example.org/très/long/chemin/vers/une/source.json"
        workspace.data["candidates"] = [
            {
                "id": "candidate-1",
                "universeId": "warframe",
                "kind": "website",
                "location": location,
                "title": "Titre court",
                "score": 0.8,
                "status": "proposed",
                "proof": "découverte",
            }
        ]
        widget = candidates_view(workspace, workspace.get("warframe"), lambda: None)
        table = widget.findChild(SimpleTable)
        self.assertIsNotNone(table)
        assert table is not None
        self.assertEqual(table.model_data.horizontalHeaderItem(0).text(), "Emplacement")
        self.assertFalse(table.horizontalHeader().isHidden())
        item = table.model_data.item(0, 0)
        assert item is not None
        self.assertEqual(item.text(), location)
        self.assertEqual(item.toolTip(), location)
        self.assertTrue(item.textAlignment() & Qt.AlignmentFlag.AlignLeft)
        self.assertEqual(table.model_data.item(0, 2).text(), "Site web")
        self.assertEqual(table.model_data.item(0, 4).text(), "Proposé")


if __name__ == "__main__":
    unittest.main()
