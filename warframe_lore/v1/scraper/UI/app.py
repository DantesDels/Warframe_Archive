"""PySide6 main window for Atelier v1 — Univers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStatusBar

if TYPE_CHECKING:
    from .execution_panel import ExecutionPanel
    from .views.details import DetailPane
    from .views.header import HeaderBar
    from .views.sidebar import Sidebar

from ..settings import SettingsStore
from ..warframe_seeds import seed_warframe_sources
from .actions import commands
from .dialogs import prompt_universe_name
from .formatting import display_universe_status
from .runner_ui import handle_finished, start_execution
from .style import app_stylesheet
from .workspace import WorkshopWorkspace


class AtelierApp(QMainWindow):
    """Main desktop window with sidebar, details and live execution."""

    sidebar: Sidebar
    header: HeaderBar
    details: DetailPane
    execution: ExecutionPanel
    status_bar: QStatusBar

    def __init__(self, workspace: Any = None, data_path: Path | None = None) -> None:
        super().__init__()
        self.data_path = Path(data_path or "data/v1/workspace.json")
        self.settings_store = SettingsStore(self.data_path.parent / "settings.json")
        self.workspace = workspace or WorkshopWorkspace(path=self.data_path)
        seed_warframe_sources(self.workspace)
        self.last_plan: Any = None
        self._thread: Any = None
        self._worker: Any = None
        self._graphql_handle: Any = None
        self.setWindowTitle("Atelier v1 — Univers")
        self.resize(1200, 760)
        self.setStyleSheet(app_stylesheet())
        self._build_ui()
        self._bind_shortcuts()
        self.refresh()
        self._start_graphql_if_enabled()

    def _start_graphql_if_enabled(self) -> None:
        settings = self.settings_store.load()
        if not settings.graph_api_enabled:
            return
        try:
            from ..graph.server import start_graphql_server

            self._graphql_handle = start_graphql_server(
                self.workspace,
                host=settings.graph_api_host,
                port=settings.graph_api_port,
            )
        except Exception as error:  # noqa: BLE001
            self.status_bar.showMessage(f"GraphQL indisponible : {error}")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._graphql_handle is not None:
            self._graphql_handle.stop()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        from .app_ui import build_ui

        build_ui(self)

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
        sc = QShortcut(QKeySequence("F2"), self)
        sc.activated.connect(self.rename_universe)

    def selected_id(self) -> str | None:
        return cast(str | None, self.sidebar.selected_id())

    def on_select(self, universe_id: str | None) -> None:
        universe = (
            cast(dict[str, Any] | None, self.workspace.get(universe_id or ""))
            if universe_id
            else None
        )
        self.details.show_universe(universe, self.workspace, self.refresh_current)
        self._update_header(universe)

    def refresh(self, selected_id: str | None = None) -> None:
        universes = cast(list[dict[str, Any]], self.workspace.universes())
        current = selected_id or self.selected_id()
        self.sidebar.set_universes(universes, self.workspace)
        if current and self.workspace.get(current):
            self.sidebar.select(current)
        else:
            self.sidebar.select(None)
            self.on_select(None)
        self._update_header(
            cast(dict[str, Any] | None, self.workspace.get(self.selected_id() or ""))
        )

    def refresh_current(self) -> None:
        self.refresh(self.selected_id())

    def _update_header(self, universe: dict[str, Any] | None) -> None:
        count = len(cast(list[Any], self.workspace.universes()))
        if universe:
            status = display_universe_status(str(universe.get("status", "")))
            self.header.set_context(str(universe.get("name", "")), count, status)
        else:
            self.header.set_context(None, count, "Prêt")

    def create_universe(self) -> None:
        name = prompt_universe_name(
            self,
            title="Nouvel Univers",
            used_names=set(cast(list[str], self.workspace.names())),
        )
        if name:
            universe = cast(dict[str, Any], self.workspace.create(name))
            commands.apply_discovery(self, universe)
            self.refresh(str(universe["id"]))

    def rename_universe(self) -> None:
        universe = cast(
            dict[str, Any] | None, self.workspace.get(self.selected_id() or "")
        )
        if universe is None:
            QMessageBox.information(
                self, "Renommer", "Sélectionnez d'abord un Univers."
            )
            return
        name = prompt_universe_name(
            self,
            title="Renommer l'Univers",
            used_names=set(
                cast(list[str], self.workspace.names(exclude=str(universe["id"])))
            ),
            initial=str(universe.get("name", "")),
        )
        if name:
            self.workspace.rename(str(universe["id"]), name)
            commands.apply_discovery(self, universe)
            self.refresh(str(universe["id"]))

    def start_execution(self, plan: Any) -> None:
        start_execution(self, plan)

    def _on_execution_finished(self, result: object) -> None:
        handle_finished(self, result)
