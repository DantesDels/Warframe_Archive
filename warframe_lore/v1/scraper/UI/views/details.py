"""Right-hand detail pane driven by the selected Universe."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..formatting import display_universe_status
from .data.tabs import data_view
from .graph_view import graph_view
from .sources_view import SourcesView
from .tabs_candidates import candidates_view
from .tabs_content import documents_view, runs_view


class DetailPane(QWidget):
    """Universe details with tabbed sources/documents/runs/candidates/graph."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        top = QHBoxLayout()
        title_box = QVBoxLayout()
        self.title = QLabel("Aucun Univers sélectionné")
        self.title.setStyleSheet("font-size: 20px; font-weight: 700; color: #1e293b;")
        self.subtitle = QLabel("Sélectionnez un Univers dans l'arborescence.")
        self.subtitle.setStyleSheet("color: #475569;")
        self.subtitle.setWordWrap(True)
        title_box.addWidget(self.title)
        title_box.addWidget(self.subtitle)
        self.caps_button = QPushButton("Capacités...")
        self.caps_button.setVisible(False)
        self.caps_button.clicked.connect(self._edit_capabilities)
        top.addLayout(title_box, 1)
        top.addWidget(self.caps_button)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top)
        layout.addSpacing(8)
        layout.addWidget(self.body, 1)
        self._current: tuple[Any, dict[str, Any], Callable[[], None]] | None = None
        self.clear()

    def clear(self) -> None:
        """Reset the pane to its empty state."""
        self._current = None
        self.caps_button.setVisible(False)
        self.title.setText("Aucun Univers sélectionné")
        self.subtitle.setText("Sélectionnez un Univers dans l'arborescence.")
        self._set_content(QLabel("Les détails apparaîtront ici après sélection."))

    def _set_content(self, widget: QWidget) -> None:
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            old_widget = item.widget() if item is not None else None
            if old_widget is not None:
                old_widget.deleteLater()
        self.body_layout.addWidget(widget)

    def show_universe(
        self,
        universe: dict[str, Any] | None,
        workspace: Any,
        on_change: Callable[[], None],
    ) -> None:
        """Render all tabs for the selected universe."""
        if universe is None:
            self.clear()
            return
        self._current = (workspace, universe, on_change)
        self.caps_button.setVisible(True)
        uid = str(universe.get("id", ""))
        self.title.setText(str(universe.get("name", "")))
        status = display_universe_status(str(universe.get("status", "")))
        self.subtitle.setText(f"{universe.get('description', '')} • {status}")
        tabs = QTabWidget()
        sources = cast(list[dict[str, Any]], workspace.sources_for(uid))
        documents = cast(list[dict[str, Any]], workspace.documents_for(uid))
        runs = cast(list[dict[str, Any]], workspace.runs_for(uid))
        candidates = cast(list[dict[str, Any]], workspace.candidates_for(uid))
        tabs.addTab(
            SourcesView(workspace, universe, on_change), f"Sources ({len(sources)})"
        )
        tabs.addTab(
            documents_view(workspace, universe), f"Documents ({len(documents)})"
        )
        tabs.addTab(runs_view(workspace, universe), f"Exécutions ({len(runs)})")
        tabs.addTab(
            candidates_view(workspace, universe, on_change),
            f"Candidats ({len(candidates)})",
        )
        tabs.addTab(data_view(workspace, universe, on_change), "Data")
        tabs.addTab(graph_view(workspace, universe), "Graphe")
        self._set_content(tabs)

    def _edit_capabilities(self) -> None:
        """Open the capabilities editor for the current universe."""
        if self._current is None:
            return
        from ..dialogs.capabilities_dialog import CapabilitiesDialog

        workspace, universe, on_change = self._current
        universe_id = str(universe.get("id", ""))
        dialog = CapabilitiesDialog(
            self, workspace.capabilities_for(universe_id)
        )
        if dialog.exec() and dialog.result_capabilities is not None:
            workspace.set_capabilities(universe_id, dialog.result_capabilities)
            on_change()
