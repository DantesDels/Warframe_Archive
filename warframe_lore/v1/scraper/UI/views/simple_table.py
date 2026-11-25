"""Sortable, filterable read-only table view with optional multi-selection."""

from __future__ import annotations

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QTableView

from .location_delegate import LocationDelegate
from .table_filter import SORT_ROLE, apply_column_sizing, configure_header, sort_key

MAX_VISIBLE_ROWS = 500


class SimpleTable(QTableView):
    """Ergonomic table with sorting, filtering, tooltips and multi-select."""

    def __init__(
        self, headers: list[str], equal_columns: bool = False,
        stretch_columns: list[int] | None = None, elide_first: bool = False,
        left_columns: set[int] | None = None, multi_select: bool = False,
        column_widths: dict[int, int] | None = None,
        hidden_columns: set[int] | None = None,
    ) -> None:
        super().__init__()
        self._equal_columns, self._stretch_columns = equal_columns, stretch_columns
        self._elide_first = elide_first
        self._left_columns = left_columns if left_columns is not None else {0}
        self._column_widths = column_widths or {}
        self._hidden_columns = hidden_columns or set()
        self._all_ids: list[str] = []
        self.total_row_count = 0
        self.model_data = QStandardItemModel(0, len(headers))
        self.model_data.setHorizontalHeaderLabels(headers)
        self.proxy = QSortFilterProxyModel(
            self,
            filterCaseSensitivity=Qt.CaseSensitivity.CaseInsensitive,
            sortCaseSensitivity=Qt.CaseSensitivity.CaseInsensitive,
            filterKeyColumn=-1,
        )
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        sel = QAbstractItemView.SelectionMode
        self.setSelectionMode(
            sel.ExtendedSelection if multi_select else sel.SingleSelection
        )
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(32)
        header = self.horizontalHeader()
        header.setVisible(True)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(64)
        header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        header.sectionClicked.connect(self._ensure_sort_role)
        self.setSortingEnabled(True)
        if elide_first:
            self.setItemDelegateForColumn(0, LocationDelegate(self))
            self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.use_proxy(self.proxy)

    def use_proxy(self, proxy: QSortFilterProxyModel) -> None:
        """Attach a proxy model while preserving sort role and header modes."""
        proxy.setSourceModel(self.model_data)
        self.proxy = proxy
        self.setModel(proxy)
        configure_header(
            self.horizontalHeader(), self.model_data.columnCount(),
            equal_columns=self._equal_columns, stretch_columns=self._stretch_columns,
        )

    def _ensure_sort_role(self, column: int) -> None:
        """Populate numeric sort keys lazily for the clicked column."""
        for row_idx in range(self.model_data.rowCount()):
            item = self.model_data.item(row_idx, column)
            if item is not None and item.data(SORT_ROLE) is None:
                item.setData(sort_key(item.text()), SORT_ROLE)
        self.proxy.setSortRole(SORT_ROLE)

    def set_rows(self, rows: list[list[str]], ids: list[str] | None = None) -> None:
        """Populate up to MAX_VISIBLE_ROWS with tooltips, sort keys and widths."""
        self.total_row_count = len(rows)
        self._all_ids = [str(v) for v in ids] if ids else []
        capped_rows = rows[:MAX_VISIBLE_ROWS]
        self.proxy.setSourceModel(None)
        self.model_data.blockSignals(True)
        self.model_data.removeRows(0, self.model_data.rowCount())
        al = Qt.AlignmentFlag
        left_cols = set(self._left_columns) | ({0} if self._elide_first else set())
        full_style = len(capped_rows) <= 64
        for index, row in enumerate(capped_rows):
            items: list[QStandardItem] = []
            for column, value in enumerate(row):
                text = str(value)
                item = QStandardItem(text)
                if full_style or index == 0:
                    item.setToolTip(text)
                    h = al.AlignLeft if column in left_cols else al.AlignCenter
                    item.setTextAlignment(al.AlignVCenter | h)
                items.append(item)
            if ids and index < len(ids) and items:
                items[0].setData(ids[index], Qt.ItemDataRole.UserRole)
            self.model_data.appendRow(items)
        self.model_data.blockSignals(False)
        self.proxy.setSourceModel(self.model_data)
        apply_column_sizing(
            self, self.model_data.columnCount(), column_widths=self._column_widths,
            hidden_columns=self._hidden_columns, elide_first=self._elide_first,
        )

    def set_filter(self, query: str) -> int:
        """Filter across all columns and return the number of visible rows."""
        self.proxy.setFilterFixedString(query.strip())
        return self.proxy.rowCount()

    def selected_ids(self) -> list[str]:
        """Return all identifiers carried by the currently selected rows."""
        indexes = self.selectionModel().selectedRows() if self.selectionModel() else []
        vis = self.proxy.rowCount()
        full_sel = len(indexes) == vis == self.model_data.rowCount()
        if indexes and len(self._all_ids) > MAX_VISIBLE_ROWS and full_sel:
            return list(self._all_ids)
        out: list[str] = []
        for idx in indexes:
            item = self.model_data.item(self.proxy.mapToSource(idx).row(), 0)
            if item and item.data(Qt.ItemDataRole.UserRole) is not None:
                out.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return out

    def selected_id(self) -> str | None:
        """Return the identifier of the first selected row."""
        ids = self.selected_ids()
        return ids[0] if ids else None
