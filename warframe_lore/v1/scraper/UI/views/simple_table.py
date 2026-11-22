"""Simple read-only table view for documents, runs and candidates."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QHeaderView, QTableView


class SimpleTable(QTableView):
    """Compact table backed by a standard item model."""

    def __init__(self, headers: list[str]) -> None:
        super().__init__()
        self.model_data = QStandardItemModel(0, len(headers))
        self.model_data.setHorizontalHeaderLabels(headers)
        self.setModel(self.model_data)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSelectionMode(QTableView.SingleSelection)
        self.setEditTriggers(QTableView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)

    def set_rows(self, rows: list[list[str]], ids: list[str] | None = None) -> None:
        self.model_data.removeRows(0, self.model_data.rowCount())
        for idx, row in enumerate(rows):
            items = [QStandardItem(str(value)) for value in row]
            if ids and idx < len(ids):
                items[0].setData(ids[idx], Qt.UserRole)
            for item in items:
                item.setEditable(False)
                item.setTextAlignment(Qt.AlignCenter)
            self.model_data.appendRow(items)
        self.resizeColumnsToContents()

    def selected_id(self) -> str | None:
        indexes = self.selectionModel().selectedRows() if self.selectionModel() else []
        if not indexes:
            return None
        return self.model_data.item(indexes[0].row(), 0).data(Qt.UserRole)
