"""PySide6 main window for Atelier v1 — Univers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QStatusBar

if TYPE_CHECKING:
    from .execution_panel import ExecutionPanel
    from .views.details import DetailPane
    from .views.header import HeaderBar
    from .views.sidebar import Sidebar

from ..settings import SettingsStore
from ..warframe_seeds import seed_warframe_sources
from .actions import commands
from .formatting import display_universe_status
from .runner_ui import handle_finished, start_execution
from .runtime.app_lifecycle import start_graphql as _start_graphql
from .runtime.app_lifecycle import stop_services as _stop_services
from .style import apply_theme
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
        self.setMinimumSize(960, 620)
        from .dialogs.responsive import fit_to_screen

        fit_to_screen(self, ideal_width=1360, ideal_height=840,
                      width_ratio=0.94, height_ratio=0.90)
        apply_theme(self)
        self._build_ui()
        self._bind_shortcuts()
        self.refresh()
        _start_graphql(self)

    def closeEvent(self, event: QCloseEvent) -> None:
        _stop_services(self)
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
        sc.activated.connect(self._shortcut_rename)

    def _shortcut_rename(self) -> None:
        from PySide6.QtWidgets import QApplication, QLineEdit, QTextEdit

        if isinstance(QApplication.focusWidget(), (QLineEdit, QTextEdit)):
            return
        self.rename_universe()

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
        commands.create_universe(self)

    def rename_universe(self) -> None:
        commands.rename_universe(self)

    def start_execution(self, plan: Any) -> None:
        start_execution(self, plan)

    def _on_execution_finished(self, result: object) -> None:
        handle_finished(self, result)
