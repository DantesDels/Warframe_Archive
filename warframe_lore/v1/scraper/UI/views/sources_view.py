"""Sources tab with action bar and styled table."""

from __future__ import annotations

from PySide6.QtWidgets import QTableView, QVBoxLayout, QWidget

from .delegates import SourceDelegate
from .source_model import SourceTableModel
from .sources_actions import build_actions


class SourcesView(QWidget):
    """Interactive source management for one Universe."""

    def __init__(self, workspace, universe: dict, on_change) -> None:
        super().__init__()
        self.workspace = workspace
        self.universe = universe
        self.on_change = on_change
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(build_actions(self))
        self.model = SourceTableModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setItemDelegate(SourceDelegate(self.table))
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 420)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 140)
        layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self) -> None:
        self.model.set_sources(self.workspace.sources_for(self.universe["id"]))

    def selected_id(self) -> str | None:
        indexes = self.table.selectionModel().selectedRows()
        return self.model.source_id_at(indexes[0].row()) if indexes else None

    def current_source(self) -> dict | None:
        source_id = self.selected_id()
        return next(
            (s for s in self.workspace.data["sources"] if s["id"] == source_id),
            None,
        )
