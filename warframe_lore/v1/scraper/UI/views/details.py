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

from ...gaps import gaps_for
from ...self_heal import quarantined_count
from ...truth import open_conflicts_count
from ..formatting import display_universe_status
from .conflicts import conflicts_view
from .data.tabs import data_view
from .gaps import gaps_view
from .graph_view import graph_view
from .self_heal import self_heal_view
from .sources_view import SourcesView
from .tabs_candidates import candidates_view
from .tabs_content import documents_view, runs_view
from .watch import watch_view


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
        self._active_tab_index = 0
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
                old_widget.setParent(None)
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
        tabs.setUsesScrollButtons(True)
        tabs.tabBar().setExpanding(False)
        sources = cast(list[dict[str, Any]], workspace.sources_for(uid))
        docs = cast(list[dict[str, Any]], workspace.documents_for(uid))
        runs = cast(list[dict[str, Any]], workspace.runs_for(uid))
        cands = cast(list[dict[str, Any]], workspace.candidates_for(uid))
        gaps = gaps_for(workspace, uid)
        open_c = open_conflicts_count(workspace, uid)
        quar_n = quarantined_count(workspace, uid)
        c_view = candidates_view(workspace, universe, on_change)
        sh_view = self_heal_view(workspace, universe, on_change)
        specs = (
            (SourcesView(workspace, universe, on_change), f"Sources ({len(sources)})"),
            (documents_view(workspace, universe), f"Documents ({len(docs)})"),
            (runs_view(workspace, universe), f"Exécutions ({len(runs)})"),
            (c_view, f"Candidats ({len(cands)})"),
            (data_view(workspace, universe, on_change), "Data"),
            (graph_view(workspace, universe), "Graphe"),
            (watch_view(workspace, universe, on_change), "Veille"),
            (gaps_view(workspace, universe, on_change), f"Lacunes ({len(gaps)})"),
            (conflicts_view(workspace, universe, on_change), f"Conflits ({open_c})"),
            (sh_view, f"Quarantaine ({quar_n})"),
        )
        for widget, label in specs:
            tabs.addTab(widget, label)
        if 0 <= self._active_tab_index < tabs.count():
            tabs.setCurrentIndex(self._active_tab_index)
        tabs.currentChanged.connect(self._remember_tab)
        self._set_content(tabs)

    def _remember_tab(self, index: int) -> None:
        if index >= 0:
            self._active_tab_index = index

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
