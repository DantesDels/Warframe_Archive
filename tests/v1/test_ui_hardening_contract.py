"""Regression contracts for UTF-8 text, icons and execution lifecycle."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThread  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QPushButton,
    QStatusBar,
)

from warframe_lore.v1.scraper.UI import AtelierApp, WorkshopWorkspace  # noqa: E402
from warframe_lore.v1.scraper.UI.execution_panel import ExecutionPanel  # noqa: E402
from warframe_lore.v1.scraper.UI.runner_ui import (  # noqa: E402
    cleanup_execution,
)
from warframe_lore.v1.scraper.UI.style import app_stylesheet  # noqa: E402
from warframe_lore.v1.scraper.UI.views.sources_view import SourcesView  # noqa: E402
from warframe_lore.v1.scraper.UI.worker import ExecutionWorker  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MANGLED_TOKENS = (
    "Ex?cution",
    "Param?tres",
    "S?curit?",
    "D?couverte",
    "S?lectionnez",
    "t?l?chargement",
    "actualit?s",
    "configur?e",
    "v?rifi?e",
    "autoris?.",
    "H?te",
    "Sch?ma",
    "donn?es",
    "Annul?",
    "Pr?t",
    "Termin?",
)


def _qt_app() -> QApplication:
    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _make_app(tmp: str) -> AtelierApp:
    path = Path(tmp) / "workspace.json"
    return AtelierApp(WorkshopWorkspace(path=path), path)


class EncodingContractTests(unittest.TestCase):
    def test_sources_are_utf8_without_mangled_accents(self) -> None:
        offenders: list[str] = []
        for folder in ("warframe_lore/v1", "tests/v1"):
            for path in (ROOT / folder).rglob("*.py"):
                if path.name == Path(__file__).name:
                    continue  # this module lists the forbidden tokens on purpose
                text = path.read_text(encoding="utf-8")
                offenders.extend(
                    f"{path.relative_to(ROOT)}:{token}"
                    for token in MANGLED_TOKENS
                    if token in text
                )
        self.assertEqual(offenders, [])


class FeedbackContractTests(unittest.TestCase):
    def test_stylesheet_defines_pressed_feedback(self) -> None:
        stylesheet = app_stylesheet()
        self.assertIn("QPushButton:pressed", stylesheet)
        self.assertIn("QPushButton#SidebarIconButton:pressed", stylesheet)
        self.assertIn("QPushButton:disabled", stylesheet)

    def test_standard_icons_replace_font_glyphs(self) -> None:
        _qt_app()
        with tempfile.TemporaryDirectory() as tmp:
            app = _make_app(tmp)
            buttons = [
                button
                for button in app.sidebar.findChildren(QPushButton)
                if button.objectName() == "SidebarIconButton"
            ]
            self.assertTrue(buttons)
            self.assertTrue(all(not button.icon().isNull() for button in buttons))
            self.assertTrue(all(not button.text() for button in buttons))
            app.close()
            app.deleteLater()

    def test_explicit_vector_icons_are_distinct_and_non_empty(self) -> None:
        from warframe_lore.v1.scraper.UI.views.sidebar_btn import vector_icon

        _qt_app()
        signatures: dict[str, bytes] = {}
        for name in ("rename", "settings", "sync", "add", "execute", "delete"):
            icon = vector_icon(name, 32)
            self.assertFalse(icon.isNull(), name)
            img = icon.pixmap(32, 32).toImage()
            raw = bytes(img.constBits())
            self.assertTrue(any(raw), f"empty icon: {name}")
            signatures[name] = raw
        self.assertEqual(len(set(signatures.values())), 6)


class LifecycleContractTests(unittest.TestCase):
    def test_cleanup_disconnects_control_slots(self) -> None:
        calls: list[int] = []
        slot = lambda: calls.append(1)  # noqa: E731
        button = QPushButton("x")
        button.clicked.connect(slot)
        app = SimpleNamespace(_control_connections=[(button, slot)])
        cleanup_execution(app)
        button.click()
        self.assertEqual(calls, [])
        self.assertIsNone(app._thread)
        self.assertIsNone(app._worker)

    def test_launch_while_running_keeps_the_current_thread(self) -> None:
        _qt_app()
        with tempfile.TemporaryDirectory() as tmp:
            app = _make_app(tmp)
            thread = QThread()
            thread.start()
            app._thread = thread
            app.start_execution(object())
            self.assertEqual(
                app.status_bar.currentMessage(),
                "Statut : Exécution déjà en cours",
            )
            thread.quit()
            thread.wait(1000)
            app.close()
            app.deleteLater()

    def test_worker_http_calls_are_time_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worker = ExecutionWorker(
                SimpleNamespace(settings=None, universe_ids=()),
                SimpleNamespace(),
                Path(tmp) / "exports",
            )
            self.assertEqual(worker.client.timeout, (5.0, 15.0))
            self.assertEqual(worker.client.max_retries, 2)


class ExecutionStateContractTests(unittest.TestCase):
    def test_label_progress_and_status_bar_share_one_state_handler(self) -> None:
        _qt_app()
        panel = ExecutionPanel()
        status_bar = QStatusBar()
        panel.set_status_bar(status_bar)

        panel.set_state("running")
        self.assertNotIn("Aucune exécution en cours.", panel.step_label.text())
        self.assertEqual(status_bar.currentMessage(), "Statut : Exécution en cours")
        self.assertTrue(panel.cancel_btn.isEnabled())

        panel.set_state("idle")
        self.assertEqual(panel.step_label.text(), "Aucune exécution en cours.")
        self.assertEqual(panel.progress.value(), 0)
        self.assertEqual(status_bar.currentMessage(), "Statut : Prêt")

    def test_app_never_shows_idle_label_during_a_run(self) -> None:
        _qt_app()
        with tempfile.TemporaryDirectory() as tmp:
            app = _make_app(tmp)
            self.assertEqual(
                app.execution.step_label.text(), "Aucune exécution en cours."
            )
            app.execution.set_state("running", "Préparation de l'exécution...")
            self.assertNotEqual(
                app.execution.step_label.text(), "Aucune exécution en cours."
            )
            self.assertEqual(
                app.status_bar.currentMessage(), "Statut : Exécution en cours"
            )
            app.close()
            app.deleteLater()


class LocalSourceUiContractTests(unittest.TestCase):
    def test_sources_tab_can_import_a_directory_as_a_source(self) -> None:
        _qt_app()
        with tempfile.TemporaryDirectory() as tmp:
            workspace = WorkshopWorkspace(path=Path(tmp) / "workspace.json")
            workspace.create("Univers")
            app = AtelierApp(workspace, workspace.path)
            app.sidebar.select("univers")
            QApplication.processEvents()
            view = app.details.findChild(SourcesView)
            self.assertIsNotNone(view)
            assert view is not None
            button = next(
                item
                for item in view.findChildren(QPushButton)
                if item.text() == "+ Importer dossier"
            )
            target = str(Path(tmp) / "corpus")
            with patch(
                "warframe_lore.v1.scraper.UI.views.sources_actions.QFileDialog"
                ".getExistingDirectory",
                return_value=target,
            ):
                button.click()
            added = [
                source
                for source in workspace.sources_for("univers")
                if source.get("location") == target
            ]
            self.assertEqual(len(added), 1)
            self.assertEqual(added[0]["kind"], "local_directory")
            app.close()
            app.deleteLater()


if __name__ == "__main__":
    unittest.main()
