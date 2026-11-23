"""Sortable, filterable read-only table view with optional multi-selection."""

from __future__ import annotations

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QTableView

from .location_delegate import LocationDelegate
from .table_filter import SORT_ROLE, apply_column_sizing, configure_header, sort_key


class SimpleTable(QTableView):
    """Ergonomic table with sorting, filtering, tooltips and multi-select."""

    def __init__(
        self,
        headers: list[str],
        equal_columns: bool = False,
        stretch_columns: list[int] | None = None,
        elide_first: bool = False,
        left_columns: set[int] | None = None,
        multi_select: bool = False,
        column_widths: dict[int, int] | None = None,
        hidden_columns: set[int] | None = None,
    ) -> None:
        super().__init__()
        self._equal_columns = equal_columns
        self._stretch_columns = stretch_columns
        self._elide_first = elide_first
        self._left_columns = left_columns if left_columns is not None else {0}
        self._column_widths = column_widths or {}
        self._hidden_columns = hidden_columns or set()
        self.model_data = QStandardItemModel(0, len(headers))
        self.model_data.setHorizontalHeaderLabels(headers)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        sel = QAbstractItemView.SelectionMode
        self.setSelectionMode(
            sel.ExtendedSelection if multi_select else sel.SingleSelection
        )
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(32)
        header = self.horizontalHeader()
        header.setVisible(True)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(64)
        if elide_first:
            self.setItemDelegateForColumn(0, LocationDelegate(self))
            self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.use_proxy(self.proxy)

    def use_proxy(self, proxy: QSortFilterProxyModel) -> None:
        """Attach a proxy model while preserving sort role and header modes."""
        proxy.setSourceModel(self.model_data)
        proxy.setSortRole(SORT_ROLE)
        self.proxy = proxy
        self.setModel(proxy)
        configure_header(
            self.horizontalHeader(),
            self.model_data.columnCount(),
            equal_columns=self._equal_columns,
            stretch_columns=self._stretch_columns,
        )

    def set_rows(self, rows: list[list[str]], ids: list[str] | None = None) -> None:
        """Populate rows with tooltips, numeric sort keys and compact widths."""
        self.setSortingEnabled(False)
        self.model_data.removeRows(0, self.model_data.rowCount())
        for index, row in enumerate(rows):
            items = [QStandardItem(str(value)) for value in row]
            if ids and index < len(ids):
                items[0].setData(ids[index], Qt.ItemDataRole.UserRole)
            for column, item in enumerate(items):
                text = item.text()
                item.setEditable(False)
                item.setData(sort_key(text), SORT_ROLE)
                item.setToolTip(text)
                left = column in self._left_columns or (
                    self._elide_first and column == 0
                )
                al = Qt.AlignmentFlag
                h = al.AlignLeft if left else al.AlignCenter
                item.setTextAlignment(al.AlignVCenter | h)
            self.model_data.appendRow(items)
        apply_column_sizing(
            self, self.model_data.columnCount(), column_widths=self._column_widths,
            hidden_columns=self._hidden_columns, elide_first=self._elide_first,
        )
        self.setSortingEnabled(True)

    def set_filter(self, query: str) -> int:
        """Filter across all columns and return the number of visible rows."""
        self.proxy.setFilterFixedString(query.strip())
        return self.proxy.rowCount()

    def selected_ids(self) -> list[str]:
        """Return all identifiers carried by the currently selected rows."""
        indexes = self.selectionModel().selectedRows() if self.selectionModel() else []
        result: list[str] = []
        for idx in indexes:
            src_row = self.proxy.mapToSource(idx).row()
            item = self.model_data.item(src_row, 0)
            value = item.data(Qt.ItemDataRole.UserRole) if item else None
            if value is not None:
                result.append(str(value))
        return result

    def selected_id(self) -> str | None:
        """Return the identifier of the first selected row."""
        ids = self.selected_ids()
        return ids[0] if ids else None
