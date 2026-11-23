"""Sources tab with action bar and styled table."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtWidgets import QAbstractItemView, QTableView, QVBoxLayout, QWidget

from .delegates import SourceDelegate
from .source_model import SourceTableModel
from .sources_actions import build_actions


class SourcesView(QWidget):
    """Interactive source management for one Universe."""

    def __init__(
        self, workspace: Any, universe: dict[str, Any], on_change: Callable[[], None]
    ) -> None:
        super().__init__()
        self.workspace = workspace
        self.universe = universe
        self.on_change = on_change
        self._suspend_btn: Any = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(build_actions(self))
        self.model = SourceTableModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setItemDelegate(SourceDelegate(self.table))
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 420)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 140)
        selection_model = self.table.selectionModel()
        if selection_model is not None:
            def _on_sel(*_args: object) -> None:
                self.sync_actions()
            selection_model.selectionChanged.connect(_on_sel)
        layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self) -> None:
        self.model.set_sources(
            cast(list[dict[str, Any]],
                self.workspace.sources_for(str(self.universe["id"])))
        )
        self.sync_actions()

    def selected_ids(self) -> list[str]:
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return []
        indexes = selection_model.selectedRows()
        ids = [self.model.source_id_at(i.row()) for i in indexes]
        return [sid for sid in ids if sid]

    def selected_id(self) -> str | None:
        ids = self.selected_ids()
        return ids[0] if ids else None

    def selected_sources(self) -> list[dict[str, Any]]:
        ids = set(self.selected_ids())
        sources = cast(list[dict[str, Any]], self.workspace.data.get("sources", []))
        return [s for s in sources if str(s.get("id")) in ids]

    def current_source(self) -> dict[str, Any] | None:
        source_id = self.selected_id()
        sources = cast(list[dict[str, Any]], self.workspace.data.get("sources", []))
        return next((s for s in sources if str(s.get("id")) == source_id), None)

    def sync_actions(self) -> None:
        if self._suspend_btn is None:
            return
        sources = self.selected_sources()
        if sources and all(str(s.get("status")) == "suspended" for s in sources):
            self._suspend_btn.setText("Activer")
        else:
            self._suspend_btn.setText("Suspendre")
