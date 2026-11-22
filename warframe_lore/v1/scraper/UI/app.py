"""PySide6 main window for Atelier v1 — Univers."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..settings import SettingsStore
from .actions import commands
from .dialogs import prompt_universe_name
from .execution_panel import ExecutionPanel
from .formatting import display_universe_status
from .runner_ui import handle_finished, start_execution
from .style import app_stylesheet
from .views import DetailPane, HeaderBar, Sidebar
from .workspace import WorkshopWorkspace

VERSION_LABEL = "Version v1.0.0-alpha • Mis à jour : 1h"


class AtelierApp(QMainWindow):
    """Main desktop window with sidebar, details and live execution."""

    def __init__(self, workspace=None, data_path: Path | None = None) -> None:
        super().__init__()
        self.data_path = Path(data_path or "data/v1/workspace.json")
        self.settings_store = SettingsStore(self.data_path.parent / "settings.json")
        self.workspace = workspace or WorkshopWorkspace(path=self.data_path)
        self.last_plan = None
        self._thread = None
        self._worker = None
        self.setWindowTitle("Atelier v1 — Univers")
        self.resize(1200, 760)
        self.setStyleSheet(app_stylesheet())
        self._build_ui()
        self._bind_shortcuts()
        self.refresh()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.header = HeaderBar()
        root.addWidget(self.header)

        splitter = QSplitter(Qt.Horizontal)
        self.sidebar = Sidebar()
        self.details = DetailPane()
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter, 1)
        self._bind_sidebar()
        self.sidebar.selection_changed.connect(self.on_select)

        self.execution = ExecutionPanel()
        root.addWidget(self.execution)
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Statut : Prêt")
        self.status_bar.addPermanentWidget(QLabel(VERSION_LABEL))
        self.setStatusBar(self.status_bar)

    def _bind_sidebar(self) -> None:
        self.sidebar.create_requested.connect(self.create_universe)
        self.sidebar.rename_requested.connect(self.rename_universe)
        self.sidebar.settings_requested.connect(
            lambda: commands.open_app_settings(self)
        )
        self.sidebar.execute_requested.connect(self._execute_universe)
        self.sidebar.sync_requested.connect(self._sync_universe)
        self.sidebar.delete_requested.connect(self._delete_universe)
        self.sidebar.sync_all_requested.connect(lambda: commands.sync_all(self))

    def _execute_universe(self, universe_id: str) -> None:
        self.sidebar.select(universe_id)
        commands.prepare_launch(self)

    def _sync_universe(self, universe_id: str) -> None:
        self.sidebar.select(universe_id)
        commands.sync_selected(self, universe_id)

    def _delete_universe(self, universe_id: str) -> None:
        self.sidebar.select(universe_id)
        commands.delete_selected(self)

    def _bind_shortcuts(self) -> None:
        QShortcut(QKeySequence("F2"), self, activated=self.rename_universe)

    def selected_id(self) -> str | None:
        return self.sidebar.selected_id()

    def on_select(self, universe_id: str | None) -> None:
        universe = self.workspace.get(universe_id or "") if universe_id else None
        self.details.show_universe(universe, self.workspace, self.refresh_current)
        self._update_header(universe)

    def refresh(self, selected_id: str | None = None) -> None:
        universes = self.workspace.universes()
        current = selected_id or self.selected_id()
        self.sidebar.set_universes(universes, self.workspace)
        if current and self.workspace.get(current):
            self.sidebar.select(current)
        else:
            self.sidebar.select(None)
            self.on_select(None)
        self._update_header(self.workspace.get(self.selected_id() or ""))

    def refresh_current(self) -> None:
        self.refresh(self.selected_id())

    def _update_header(self, universe) -> None:
        count = len(self.workspace.universes())
        if universe:
            status = display_universe_status(universe.get("status", ""))
            self.header.set_context(universe["name"], count, status)
        else:
            self.header.set_context(None, count, "Prêt")

    def create_universe(self) -> None:
        name = prompt_universe_name(
            self,
            title="Nouvel Univers",
            used_names=self.workspace.names(),
        )
        if name:
            universe = self.workspace.create(name)
            commands.apply_discovery(self, universe)
            self.refresh(universe["id"])

    def rename_universe(self) -> None:
        universe = self.workspace.get(self.selected_id() or "")
        if universe is None:
            QMessageBox.information(
                self, "Renommer", "Sélectionnez d'abord un Univers."
            )
            return
        name = prompt_universe_name(
            self,
            title="Renommer l'Univers",
            used_names=self.workspace.names(exclude=universe["id"]),
            initial=universe["name"],
        )
        if name:
            self.workspace.rename(universe["id"], name)
            commands.apply_discovery(self, universe)
            self.refresh(universe["id"])

    def start_execution(self, plan) -> None:
        start_execution(self, plan)

    def _on_execution_finished(self, result) -> None:
        handle_finished(self, result)
