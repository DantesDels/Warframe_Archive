"""Table model for sources of a selected Universe."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

COLUMNS = [
    "Emplacement (URL/Path)",
    "Type",
    "Statut",
    "Pertinence",
]


class SourceTableModel(QAbstractTableModel):
    """Read-only table model exposing workspace source records."""

    def __init__(self, sources: list[dict] | None = None) -> None:
        super().__init__()
        self._sources = list(sources or [])

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent and parent.isValid():
            return 0
        return len(self._sources)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent and parent.isValid():
            return 0
        return len(COLUMNS)

    def headerData(self, section: int, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(COLUMNS):
            return COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._sources)):
            return None
        source = self._sources[index.row()]
        col = index.column()
        if role == Qt.UserRole:
            return source
        if role == Qt.DisplayRole and col in (0, 1):
            return source.get("location", "") if col == 0 else source.get("kind", "")
        if role == Qt.DisplayRole and col in (2, 3):
            return source.get("status", "") if col == 2 else source.get("score", 0)
        if role == Qt.ToolTipRole and col == 0:
            return source.get("location", "")
        return None

    def set_sources(self, sources: list[dict]) -> None:
        self.beginResetModel()
        self._sources = list(sources)
        self.endResetModel()

    def source_at(self, row: int) -> dict | None:
        if 0 <= row < len(self._sources):
            return self._sources[row]
        return None

    def source_id_at(self, row: int) -> str | None:
        source = self.source_at(row)
        return source["id"] if source else None
