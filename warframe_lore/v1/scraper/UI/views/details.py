"""Right-hand detail pane driven by the selected Universe."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from ..formatting import display_universe_status
from .sources_view import SourcesView
from .tabs_candidates import candidates_view
from .tabs_content import documents_view, runs_view
from .tabs_data import data_view


class DetailPane(QWidget):
    """Universe details with tabbed sources/documents/runs/candidates."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self.title = QLabel("Aucun Univers sélectionné")
        self.title.setStyleSheet("font-size: 20px; font-weight: 700; color: #1e293b;")
        self.subtitle = QLabel("Sélectionnez un Univers dans l'arborescence.")
        self.subtitle.setStyleSheet("color: #475569;")
        self.subtitle.setWordWrap(True)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addSpacing(8)
        layout.addWidget(self.body, 1)
        self.clear()

    def clear(self) -> None:
        self.title.setText("Aucun Univers sélectionné")
        self.subtitle.setText("Sélectionnez un Univers dans l'arborescence.")
        self._set_content(QLabel("Les détails apparaîtront ici après sélection."))

    def _set_content(self, widget: QWidget) -> None:
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.body_layout.addWidget(widget)

    def show_universe(self, universe, workspace, on_change) -> None:
        if universe is None:
            self.clear()
            return
        self.title.setText(universe["name"])
        status = display_universe_status(universe.get("status", ""))
        self.subtitle.setText(f"{universe.get('description', '')} • {status}")
        tabs = QTabWidget()
        sources = workspace.sources_for(universe["id"])
        docs = workspace.documents_for(universe["id"])
        runs = workspace.runs_for(universe["id"])
        cands = workspace.candidates_for(universe["id"])
        tabs.addTab(
            SourcesView(workspace, universe, on_change), f"Sources ({len(sources)})"
        )
        tabs.addTab(documents_view(workspace, universe), f"Documents ({len(docs)})")
        tabs.addTab(runs_view(workspace, universe), f"Exécutions ({len(runs)})")
        tabs.addTab(
            candidates_view(workspace, universe, on_change),
            f"Candidats ({len(cands)})",
        )
        tabs.addTab(data_view(workspace, universe), "Data")
        self._set_content(tabs)
