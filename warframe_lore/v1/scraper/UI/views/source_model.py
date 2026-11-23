"""Table model for sources of a selected Universe."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt

from ..formatting import display_kind, display_source_status

COLUMNS = [
    "Emplacement (URL/Path)",
    "Type",
    "Statut",
    "Pertinence",
]


class SourceTableModel(QAbstractTableModel):
    """Read-only table model exposing workspace source records."""

    def __init__(self, sources: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._sources = list(sources or [])

    def rowCount(
        self, parent: QModelIndex | QPersistentModelIndex | None = None
    ) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._sources)

    def columnCount(
        self, parent: QModelIndex | QPersistentModelIndex | None = None
    ) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(COLUMNS):
            return COLUMNS[section]
        return None

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._sources)):
            return None
        source = self._sources[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.UserRole:
            return source
        if role == Qt.ItemDataRole.DisplayRole and col in (0, 1):
            if col == 0:
                return source.get("location", "")
            return display_kind(str(source.get("kind", "")))
        if role == Qt.ItemDataRole.DisplayRole and col in (2, 3):
            if col == 2:
                return display_source_status(str(source.get("status", "")))
            return source.get("score", 0)
        if role == Qt.ItemDataRole.ToolTipRole and col == 0:
            return source.get("location", "")
        return None

    def set_sources(self, sources: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._sources = list(sources)
        self.endResetModel()

    def source_at(self, row: int) -> dict[str, Any] | None:
        if 0 <= row < len(self._sources):
            return self._sources[row]
        return None

    def source_id_at(self, row: int) -> str | None:
        source = self.source_at(row)
        return str(source.get("id")) if source and source.get("id") else None
