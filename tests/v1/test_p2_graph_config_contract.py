"""P2 contracts: configurable adapters, optional NLP and graph/GraphQL."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from warframe_lore.v1.scraper.discovery.providers import (  # noqa: E402
    build_default_providers,
)
from warframe_lore.v1.scraper.graph import build_graph, build_schema  # noqa: E402
from warframe_lore.v1.scraper.graph.export import export_graph  # noqa: E402
from warframe_lore.v1.scraper.graph.run_graph import write_run_graph  # noqa: E402
from warframe_lore.v1.scraper.settings import Settings, SettingsStore  # noqa: E402
from warframe_lore.v1.scraper.UI import WorkshopWorkspace, empty_data  # noqa: E402
from warframe_lore.v1.scraper.UI.dialogs.capabilities_dialog import (  # noqa: E402
    CapabilitiesDialog,
)
from warframe_lore.v1.scraper.UI.dialogs.settings_dialog import (  # noqa: E402
    SettingsDialog,
)
from warframe_lore.v1.scraper.use_cases.discover_universe import (  # noqa: E402
    discover_universe,
)
from warframe_lore.v1.scraper.use_cases.pipeline.readability import (  # noqa: E402
    readable_text,
)


def _workspace() -> WorkshopWorkspace:
    workspace = WorkshopWorkspace(data=empty_data())
    workspace.create("Codex", "Univers de fantasy")
    workspace.add_manual_source("codex", "https://codex.example/wiki", kind="wiki")
    workspace.data["documents"].append(
        {
            "id": "doc-1",
            "universeId": "codex",
            "sourceId": "https://codex.example/wiki",
            "title": "Lore",
            "url": "https://codex.example/wiki/Lore",
        }
    )
    workspace.data["candidates"].append(
        {
            "id": "cand-1",
            "universeId": "codex",
            "title": "Codex API",
            "location": "https://codex.example/api",
            "status": "proposed",
            "score": 0.8,
        }
    )
    return workspace


class GraphContractTests(unittest.TestCase):
    def test_build_graph_from_workspace(self):
        graph = build_graph(_workspace(), universe_id="codex")
        kinds = {node["kind"] for node in graph["nodes"]}
        relations = {edge["type"] for edge in graph["edges"]}
        self.assertEqual(kinds, {"Universe", "Source", "Document", "Candidate"})
        self.assertTrue(
            {"HAS_SOURCE", "HAS_DOCUMENT", "PRODUCED", "HAS_CANDIDATE"} <= relations
        )

    def test_build_graph_scoped_to_universe(self):
        graph = build_graph(_workspace(), universe_id="other")
        self.assertEqual(graph["nodes"], [])
        self.assertEqual(graph["edges"], [])

    def test_export_graph_writes_json_and_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "graph"
            paths = export_graph(out_dir, build_graph(_workspace()))
            names = [path.name for path in paths]
            self.assertEqual(names, ["graph.json", "graph.html"])
            payload = json.loads(paths[0].read_text(encoding="utf-8"))
            self.assertTrue(payload["nodes"])
            html = paths[1].read_text(encoding="utf-8")
            self.assertIn("Atelier v1", html)
            self.assertIn("Universe:codex", html)
            self.assertNotIn("__GRAPH_DATA__", html)

    def test_graphql_schema_exposes_graph(self):
        schema = build_schema(_workspace())
        result = asyncio.run(
            schema.execute("{ graph { nodes { id kind } edges { type } } }")
        )
        self.assertIsNone(result.errors)
        nodes = result.data["graph"]["nodes"]
        self.assertTrue(any(node["kind"] == "Document" for node in nodes))

    def test_graphql_schema_exposes_universes(self):
        schema = build_schema(_workspace())
        result = asyncio.run(schema.execute("{ universes { id label } }"))
        self.assertIsNone(result.errors)
        self.assertEqual(result.data["universes"][0]["label"], "Codex")

    def test_write_run_graph_from_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "run"
            paths = write_run_graph(
                out_dir,
                {"id": "codex", "name": "Codex"},
                [
                    {
                        "id": "doc-1",
                        "sourceId": "src-1",
                        "title": "Lore",
                        "url": "https://codex.example/lore",
                    }
                ],
            )
            graph = json.loads((out_dir / "graph.json").read_text(encoding="utf-8"))
            self.assertEqual(len(paths), 2)
            self.assertTrue(
                any(edge["type"] == "PRODUCED" for edge in graph["edges"])
            )


class ConfigContractTests(unittest.TestCase):
    def test_build_default_providers_passes_configuration(self):
        providers = build_default_providers(
            {
                "discovery_web_search": True,
                "discovery_web_search_url": "https://search/q={query}",
                "discovery_web_search_headers": [("Authorization", "Bearer x")],
                "discovery_git": True,
                "discovery_git_token": "secret",
                "discovery_wiki": True,
                "discovery_wiki_api_urls": ("https://wiki/api.php",),
                "discovery_sitemaps": False,
                "discovery_feeds": False,
            }
        )
        by_name = {
            type(provider).__name__: provider for provider in providers
        }
        self.assertEqual(
            by_name["WebSearchProvider"].headers, {"Authorization": "Bearer x"}
        )
        self.assertEqual(by_name["GitProvider"].token, "secret")
        self.assertEqual(
            by_name["WikiProvider"].api_urls, ("https://wiki/api.php",)
        )

    def test_settings_store_round_trip_graph_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp) / "settings.json")
            settings = Settings(
                discovery_web_search_headers=(("X-Key", "value"),),
                discovery_git_token="token",
                discovery_wiki_api_urls=("https://wiki/api.php",),
                graph_enabled=True,
                graph_api_enabled=True,
                graph_api_host="0.0.0.0",
                graph_api_port=9999,
            )
            store.save(settings)
            self.assertEqual(store.load(), settings)

    def test_discover_universe_forwards_dataclass_settings(self):
        workspace = WorkshopWorkspace(data=empty_data())
        workspace.create("Codex")
        settings = Settings(
            discovery_web_search=True,
            discovery_web_search_headers=(("X-Key", "value"),),
        )
        with patch(
            "warframe_lore.v1.scraper.use_cases.discover_universe.discover",
            return_value=[],
        ) as discover_mock:
            discover_universe(workspace, workspace.get("codex"), settings)
        config = discover_mock.call_args.kwargs["settings"]
        self.assertTrue(config["discovery_web_search"])
        self.assertEqual(config["discovery_web_search_headers"], (("X-Key", "value"),))

    def test_readable_text_falls_back_to_normalized_content(self):
        class Page:
            content = "Texte normalisé"
            raw = None
            content_type = "text/html"

        self.assertEqual(readable_text(Page()), "Texte normalisé")  # type: ignore[arg-type]

    def test_settings_dialog_exposes_advanced_fields(self):
        if QApplication.instance() is None:
            QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp) / "settings.json")
            dialog = SettingsDialog(None, store)
            dialog.advanced.search_headers.setText("Authorization: Bearer x")
            dialog.advanced.graph_api_host.setText("localhost")
            dialog.advanced.graph_api_port.setValue(9000)
            dialog.advanced.graph_api_enabled.setChecked(True)
            settings = dialog.build_settings()
            self.assertEqual(
                settings.discovery_web_search_headers, (("Authorization", "Bearer x"),)
            )
            self.assertTrue(settings.graph_api_enabled)
            self.assertEqual(settings.graph_api_host, "localhost")
            self.assertEqual(settings.graph_api_port, 9000)
            dialog.deleteLater()

    def test_capabilities_dialog_saves_budget(self):
        if QApplication.instance() is None:
            QApplication([])
        dialog = CapabilitiesDialog(None, {})
        dialog._spinboxes["max_pages"].setValue(120)
        dialog._toggles["graph_rag"].setChecked(True)
        dialog._save()
        self.assertIsNotNone(dialog.result_capabilities)
        assert dialog.result_capabilities is not None
        self.assertEqual(dialog.result_capabilities["crawl"]["max_pages"], 120)
        self.assertTrue(dialog.result_capabilities["graph_rag"]["enabled"])
        dialog.deleteLater()

    def test_capabilities_modes_and_tags_persist(self):
        if QApplication.instance() is None:
            QApplication([])
        dialog = CapabilitiesDialog(None, {})
        idx = dialog.mode_combo.findData("thematic")
        self.assertGreaterEqual(idx, 0)
        dialog.mode_combo.setCurrentIndex(idx)
        self.assertEqual(dialog._spinboxes["max_pages"].value(), 500)
        dialog.tags_input.setText("Lore, Quests; Characters, Lore")
        dialog._save()
        assert dialog.result_capabilities is not None
        crawl = dialog.result_capabilities["crawl"]
        self.assertEqual(crawl["mode"], "thematic")
        self.assertEqual(crawl["topic_tags"], ["Lore", "Quests", "Characters"])
        ex_idx = dialog.mode_combo.findData("exhaustive")
        dialog.mode_combo.setCurrentIndex(ex_idx)
        self.assertEqual(dialog._spinboxes["max_pages"].value(), 25000)
        self.assertEqual(dialog._spinboxes["source_timeout_seconds"].value(), 0)
        dialog.deleteLater()

    def test_dialogs_are_scrollable_and_execution_panel_never_overflows(self):
        from PySide6.QtWidgets import QScrollArea

        from warframe_lore.v1.scraper.observability.progress import (
            ProgressEvent,
            ProgressReporter,
        )
        from warframe_lore.v1.scraper.UI.dialogs.preflight_dialog import (
            PreflightDialog,
        )
        from warframe_lore.v1.scraper.UI.execution_panel import ExecutionPanel

        if QApplication.instance() is None:
            QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp) / "settings.json")
            for dlg in (
                SettingsDialog(None, store),
                CapabilitiesDialog(None, {}),
                PreflightDialog(None, Settings(), ("u1",), 1),
            ):
                self.assertTrue(dlg.findChildren(QScrollArea))
                dlg.deleteLater()
        panel = ExecutionPanel()
        panel.resize(900, 260)
        panel.set_state("running")
        huge_url = "https://wiki.example.com/api.php?action=query&titles=" + "|".join(
            f"VeryLongPageTitle{i}" for i in range(60)
        )
        events: list[ProgressEvent] = []
        ProgressReporter(events.append).http(huge_url, 200)
        self.assertIn("lot de 60 pages", events[0].message)
        panel.on_event(events[0])
        self.assertLessEqual(panel.minimumSizeHint().width(), 900)
        panel.deleteLater()

    def test_high_contrast_theme_and_interactive_tag_editor(self):
        from PySide6.QtGui import QPalette
        from PySide6.QtWidgets import QPushButton

        from warframe_lore.v1.scraper.UI.style import app_stylesheet, light_palette

        if QApplication.instance() is None:
            QApplication([])
        css = app_stylesheet()
        for token in (
            "QScrollArea", "QComboBox", "QComboBox QAbstractItemView",
            "QGroupBox", "alternate-background-color", "QPushButton#TagChip",
        ):
            self.assertIn(token, css)
        pal = light_palette()
        self.assertGreater(pal.color(QPalette.ColorRole.Window).lightness(), 230)
        self.assertGreater(pal.color(QPalette.ColorRole.Base).lightness(), 240)
        self.assertLess(pal.color(QPalette.ColorRole.Text).lightness(), 40)

        dialog = CapabilitiesDialog(None, {"crawl": {"topic_tags": ["Lore", "Quests"]}})
        dialog.tag_editor.input.setText("Weapons, Lore")
        dialog.tag_editor.add_button.click()
        self.assertEqual(dialog.tag_editor.tags(), ["Lore", "Quests", "Weapons"])
        chips = [
            b for b in dialog.tag_editor.findChildren(QPushButton)
            if b.objectName() == "TagChip"
        ]
        self.assertEqual(len(chips), 3)
        chips[1].click()  # remove "Quests"
        self.assertEqual(dialog.tag_editor.tags(), ["Lore", "Weapons"])
        dialog._save()
        assert dialog.result_capabilities is not None
        self.assertEqual(
            dialog.result_capabilities["crawl"]["topic_tags"], ["Lore", "Weapons"]
        )
        dialog.tag_editor.clear_button.click()
        self.assertEqual(dialog.tag_editor.tags(), [])
        dialog.deleteLater()

    def test_clear_universe_data_resets_only_target_universe(self):
        from PySide6.QtWidgets import QPlainTextEdit, QPushButton

        from warframe_lore.v1.scraper.UI.views.data.cleanup import clear_universe_data
        from warframe_lore.v1.scraper.UI.views.data.tabs import data_view

        if QApplication.instance() is None:
            QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ws = WorkshopWorkspace(path=base / "workspace.json")
            ws.create("Alpha")
            ws.create("Beta")
            ws.add_manual_source("alpha", "https://alpha.example/wiki", kind="wiki")
            ws.data["sources"][0]["connector_state"] = {"rev": 99}
            local_dir = base / "user_corpus"
            local_dir.mkdir()
            (local_dir / "keep.md").write_text("keep", encoding="utf-8")
            ws.add_manual_source("alpha", str(local_dir), kind="local_directory")
            blobs = base / "blobs"
            blobs.mkdir()
            (blobs / "a.txt").write_text("alpha", encoding="utf-8")
            (blobs / "b.txt").write_text("beta", encoding="utf-8")
            ws.data["documents"] = [
                {"id": "d1", "universeId": "alpha", "blobPath": "blobs/a.txt"},
                {"id": "d2", "universeId": "beta", "blobPath": "blobs/b.txt"},
            ]
            ws.data["document_versions"] = [
                {"universeId": "alpha", "documentId": "d1"},
                {"universeId": "beta", "documentId": "d2"},
            ]
            ws.data["runs"] = [
                {"id": "r1", "universeIds": ["alpha"]},
                {"id": "r2", "universeIds": ["alpha", "beta"]},
            ]
            exp_alpha = base / "exports" / "alpha"
            exp_alpha.mkdir(parents=True)
            (exp_alpha / "out.json").write_text("{}", encoding="utf-8")

            tab = data_view(ws, ws.get("alpha"))
            self.assertIsNotNone(tab.findChild(QPushButton, "DangerButton"))
            self.assertIsNotNone(tab.findChild(QPlainTextEdit, "DataPreview"))
            tab.deleteLater()

            stats = clear_universe_data(ws, "alpha")
            self.assertEqual(stats["documents"], 1)
            self.assertEqual(stats["blobs"], 1)
            self.assertEqual(stats["files"], 1)
            self.assertEqual(ws.documents_for("alpha"), [])
            self.assertEqual(len(ws.documents_for("beta")), 1)
            self.assertEqual(len(ws.sources_for("alpha")), 2)
            self.assertNotIn("connector_state", ws.sources_for("alpha")[0])
            self.assertFalse((blobs / "a.txt").exists())
            self.assertTrue((blobs / "b.txt").exists())
            self.assertFalse(exp_alpha.exists())
            self.assertTrue((local_dir / "keep.md").exists())
            self.assertEqual(len(ws.runs_for("alpha")), 0)
            self.assertEqual(len(ws.runs_for("beta")), 1)

    def test_table_filtering_sorting_and_graphify_controls(self):
        from PySide6.QtWidgets import QLineEdit, QPushButton

        from warframe_lore.v1.scraper.UI.graph.view import GraphCanvas
        from warframe_lore.v1.scraper.UI.views.sources_view import SourcesView
        from warframe_lore.v1.scraper.UI.views.tabs_content import documents_view

        if QApplication.instance() is None:
            QApplication([])
        ws = _workspace()
        ws.add_manual_source("codex", "https://other.example/news", kind="website")
        sv = SourcesView(ws, ws.get("codex"), lambda: None)
        self.assertTrue(sv.table.isSortingEnabled())
        sv.filter_input.setText("other.example")
        self.assertEqual(sv.proxy.rowCount(), 1)
        sv.table.selectRow(0)
        self.assertEqual(len(sv.selected_ids()), 1)
        self.assertEqual(sv.current_source()["location"], "https://other.example/news")
        sv.deleteLater()

        dv = documents_view(ws, ws.get("codex"))
        self.assertIsNotNone(dv.findChild(QLineEdit, "TableFilterInput"))
        dv.deleteLater()

        graph = build_graph(ws, universe_id="codex")
        canvas = GraphCanvas(graph)
        self.assertIsNotNone(canvas.findChild(QPushButton, "GraphFullscreenButton"))
        self.assertIsNotNone(canvas.findChild(QPushButton, "GraphOpenHtmlButton"))
        self.assertIsNotNone(canvas.findChild(QLineEdit, "GraphSearchInput"))
        initial_count = len(canvas._node_items)
        canvas.sidebar.checks["Document"].setChecked(False)
        self.assertLess(len(canvas._node_items), initial_count)
        canvas.deleteLater()


if __name__ == "__main__":
    unittest.main()
