"""Simple read-only table view for documents, runs and candidates."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView

from .location_delegate import LocationDelegate


class SimpleTable(QTableView):
    """Compact table backed by a standard item model."""

    def __init__(
        self,
        headers: list[str],
        equal_columns: bool = False,
        stretch_columns: list[int] | None = None,
        elide_first: bool = False,
    ) -> None:
        super().__init__()
        self._equal_columns = equal_columns
        self._stretch_columns = stretch_columns
        self._elide_first = elide_first
        self.model_data = QStandardItemModel(0, len(headers))
        self.model_data.setHorizontalHeaderLabels(headers)
        self.setModel(self.model_data)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        header = self.horizontalHeader()
        header.setVisible(True)
        header.setStretchLastSection(False)
        if elide_first:
            self.setItemDelegateForColumn(0, LocationDelegate(self))
            self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        if equal_columns:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        elif stretch_columns:
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            for column in stretch_columns:
                if 0 <= column < len(headers):
                    header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        else:
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

    def set_rows(self, rows: list[list[str]], ids: list[str] | None = None) -> None:
        """Populate rows with initial sizing, tooltips and aligned text."""
        self.model_data.removeRows(0, self.model_data.rowCount())
        for index, row in enumerate(rows):
            items = [QStandardItem(str(value)) for value in row]
            if ids and index < len(ids):
                items[0].setData(ids[index], Qt.ItemDataRole.UserRole)
            for column, item in enumerate(items):
                item.setEditable(False)
                left = self._elide_first and column == 0
                alignment = (
                    Qt.AlignmentFlag.AlignLeft
                    if left
                    else Qt.AlignmentFlag.AlignCenter
                )
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | alignment
                )
                if left:
                    item.setData(item.text(), Qt.ItemDataRole.ToolTipRole)
            self.model_data.appendRow(items)
        self.resizeColumnsToContents()
        if self._elide_first:
            self.horizontalHeader().setMinimumSectionSize(140)
            self.setColumnWidth(0, max(240, self.columnWidth(0)))
            self.horizontalScrollBar().setValue(0)

    def selected_id(self) -> str | None:
        """Return the identifier carried by the selected row."""
        indexes = self.selectionModel().selectedRows() if self.selectionModel() else []
        if not indexes:
            return None
        item = self.model_data.item(indexes[0].row(), 0)
        value = item.data(Qt.ItemDataRole.UserRole) if item else None
        return str(value) if value is not None else None
